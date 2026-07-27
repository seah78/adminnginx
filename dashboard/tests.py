from django.test import SimpleTestCase

from .generator import (
    generate_docker_compose,
    generate_nginx_https_vhost,
    generate_nginx_vhost,
)


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
