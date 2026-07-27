import os

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .generator import (
    APPLICATION_NETWORK,
    explain_compose_failure,
    generate_docker_compose,
    generate_nginx_https_vhost,
    generate_nginx_vhost,
    run_application_compose,
    verify_application_container,
)
from .provisioner import provision_site_live
from .version import get_version_info


class MediaGenerationTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "project_name": "example",
            "ghcr_image": "ghcr.io/example/example:latest",
            "container_name": "example",
            "internal_port": 8000,
            "domain": "example.com",
            "include_www": True,
            "enable_media": True,
        }

    def test_compose_mounts_external_media_volume(self):
        content = generate_docker_compose(self.data)

        self.assertIn("webapps_media:/app/media", content)
        self.assertIn("volumes:\n  webapps_media:\n    external: true", content)

    def test_http_vhost_serves_media_from_shared_volume(self):
        content = generate_nginx_vhost(self.data)

        self.assertIn("location /media/", content)
        self.assertIn("alias /srv/webapps-media/;", content)

    def test_https_vhost_serves_media_from_shared_volume(self):
        content = generate_nginx_https_vhost(self.data)

        self.assertIn("location /media/", content)
        self.assertIn("alias /srv/webapps-media/;", content)

    def test_media_can_be_disabled(self):
        self.data["enable_media"] = False

        compose = generate_docker_compose(self.data)
        vhost = generate_nginx_https_vhost(self.data)

        self.assertNotIn("webapps_media", compose)
        self.assertNotIn("location /media/", vhost)

    def test_compose_uses_env_file_when_available(self):
        self.data["has_env_file"] = True

        compose = generate_docker_compose(self.data)

        self.assertIn("env_file:\n      - .env", compose)

    def test_compose_omits_env_file_when_unavailable(self):
        self.data["has_env_file"] = False

        compose = generate_docker_compose(self.data)

        self.assertNotIn("env_file:", compose)


class ApplicationContainerTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "project_name": "example",
            "ghcr_image": "ghcr.io/example/example:latest",
            "container_name": "example",
            "internal_port": 8000,
            "domain": "example.com",
            "include_www": False,
            "enable_media": True,
        }

    @patch("dashboard.generator.subprocess.run")
    def test_compose_project_is_started(
        self,
        run,
    ):
        compose_path = MagicMock()
        compose_path.is_file.return_value = True
        compose_path.parent = "/host/opt/example"
        compose_path.__str__.return_value = (
            "/host/opt/example/docker-compose.prod.yml"
        )
        run.return_value.returncode = 0
        run.return_value.stdout = "Container example Started"
        run.return_value.stderr = ""

        success, message = run_application_compose(compose_path, self.data)

        self.assertTrue(success)
        self.assertIn("Container example Started", message)
        command = run.call_args.args[0]
        self.assertIn("compose", command)
        self.assertIn("up", command)
        self.assertIn("--pull", command)

    @patch("dashboard.generator.subprocess.run")
    def test_compose_failure_has_actionable_message(self, run):
        compose_path = MagicMock()
        compose_path.is_file.return_value = True
        compose_path.parent = "/host/opt/example"
        compose_path.__str__.return_value = (
            "/host/opt/example/docker-compose.prod.yml"
        )
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "denied: package access denied"

        success, message = run_application_compose(compose_path, self.data)

        self.assertFalse(success)
        self.assertIn("GHCR refuse l'accès", message)
        self.assertIn("workflow GitHub Actions", message)
        self.assertIn("read:packages", message)
        self.assertIn("package access denied", message)

    def test_missing_ghcr_tag_has_specific_message(self):
        message = explain_compose_failure(
            "manifest unknown",
            self.data,
            1,
        )

        self.assertIn("tag « latest » est introuvable", message)
        self.assertIn("workflow GitHub Actions", message)

    def test_missing_external_network_has_command(self):
        message = explain_compose_failure(
            'network internal_network declared as external, but could not be found',
            self.data,
            1,
        )

        self.assertIn("docker network create internal_network", message)

    def test_missing_media_volume_has_command(self):
        message = explain_compose_failure(
            'volume "webapps_media" declared as external, but could not be found',
            self.data,
            1,
        )

        self.assertIn("docker volume create webapps_media", message)

    @patch("dashboard.generator.docker.from_env")
    def test_stopped_container_reports_logs(self, from_env):
        container = from_env.return_value.containers.get.return_value
        container.status = "exited"
        container.logs.return_value = b"configuration missing"

        success, message = verify_application_container(self.data)

        self.assertFalse(success)
        self.assertIn("état : exited", message)
        self.assertIn("configuration missing", message)

    @patch("dashboard.generator.docker.from_env")
    def test_missing_shared_network_has_clear_message(self, from_env):
        container = from_env.return_value.containers.get.return_value
        container.status = "running"
        container.attrs = {"NetworkSettings": {"Networks": {}}}

        success, message = verify_application_container(self.data)

        self.assertFalse(success)
        self.assertIn(APPLICATION_NETWORK, message)
        self.assertIn("Nginx ne pourra pas résoudre son nom", message)

    @patch("dashboard.generator.socket.create_connection")
    @patch("dashboard.generator.docker.from_env")
    def test_running_container_must_answer_on_expected_port(
        self,
        from_env,
        create_connection,
    ):
        container = from_env.return_value.containers.get.return_value
        container.status = "running"
        container.attrs = {
            "NetworkSettings": {
                "Networks": {
                    APPLICATION_NETWORK: {"IPAddress": "172.20.0.10"},
                }
            }
        }
        connection = MagicMock()
        create_connection.return_value = connection

        success, message = verify_application_container(self.data)

        self.assertTrue(success)
        self.assertIn("accessible par Nginx sur le port 8000", message)
        create_connection.assert_called_once_with(
            ("example", 8000),
            timeout=2,
        )

    @patch("dashboard.generator.APPLICATION_START_TIMEOUT", 0)
    @patch("dashboard.generator.socket.create_connection")
    @patch("dashboard.generator.docker.from_env")
    def test_unreachable_port_reports_logs_and_port(
        self,
        from_env,
        create_connection,
    ):
        container = from_env.return_value.containers.get.return_value
        container.status = "running"
        container.attrs = {
            "NetworkSettings": {
                "Networks": {
                    APPLICATION_NETWORK: {"IPAddress": "172.20.0.10"},
                }
            }
        }
        container.logs.return_value = b"gunicorn failed"
        create_connection.side_effect = ConnectionRefusedError("refused")

        success, message = verify_application_container(self.data)

        self.assertFalse(success)
        self.assertIn("port 8000 ne répond pas", message)
        self.assertIn("gunicorn failed", message)


class ProvisioningWorkflowTests(SimpleTestCase):
    @patch("dashboard.provisioner.finish_operation")
    @patch("dashboard.provisioner.run_live_step")
    def test_container_is_checked_before_vhost_creation(
        self,
        run_live_step,
        finish_operation,
    ):
        steps = []

        def stop_before_vhost(_operation_id, name, _callback):
            steps.append(name)
            return name != "Création du vhost HTTP"

        run_live_step.side_effect = stop_before_vhost
        data = {
            "project_name": "example",
            "container_name": "example",
            "domain": "example.com",
        }

        provision_site_live(data, "operation-id")

        self.assertLess(
            steps.index("Démarrage Docker Compose"),
            steps.index("Création du vhost HTTP"),
        )
        self.assertLess(
            steps.index("Vérification du conteneur et du réseau"),
            steps.index("Création du vhost HTTP"),
        )
        finish_operation.assert_called_once_with("operation-id", False)


class VersionTests(SimpleTestCase):
    @patch.dict(
        os.environ,
        {
            "ADMINNGINX_VERSION": "build-42",
            "ADMINNGINX_GIT_SHA": "abcdef1234567890",
            "ADMINNGINX_BUILD_DATE": "2026-07-27T12:00:00Z",
            "ADMINNGINX_BUILD_RUN": "123456",
            "ADMINNGINX_DEPLOYMENT_NAME": "production-paris",
        },
        clear=False,
    )
    def test_version_info_contains_build_and_deployment(self):
        info = get_version_info()

        self.assertEqual(info["version"], "build-42")
        self.assertEqual(info["git_sha"], "abcdef1234567890")
        self.assertEqual(info["short_sha"], "abcdef123456")
        self.assertEqual(info["deployment"], "production-paris")

    @patch.dict(
        os.environ,
        {
            "ADMINNGINX_VERSION": "build-42",
            "ADMINNGINX_GIT_SHA": "abcdef1234567890",
            "ADMINNGINX_DEPLOYMENT_NAME": "production-paris",
        },
        clear=False,
    )
    def test_public_version_endpoint_is_not_cached(self):
        response = self.client.get("/version/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "build-42")
        self.assertEqual(response.json()["deployment"], "production-paris")
        self.assertEqual(response["Cache-Control"], "no-store")
