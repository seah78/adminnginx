from pathlib import Path

from .generator import (
    HOST_OPT_DIR,
    NGINX_CONFIG_DIR,
    generate_docker_compose,
    generate_nginx_vhost,
    generate_nginx_https_vhost,
    get_vhost_detail,
    nginx_test,
    nginx_reload,
    run_certbot_certonly,
)

from .operation_store import (
    start_operation_step,
    update_operation_step,
    finish_operation,
)


PROTECTED_CONTAINERS = {
    "adminnginx",
    "nginx_proxy",
    "certbot",
}


def run_live_step(operation_id: str, name: str, callback) -> bool:
    step_index = start_operation_step(
        operation_id,
        name,
        "En cours...",
    )

    try:
        success, output = callback()

        update_operation_step(
            operation_id,
            step_index,
            "success" if success else "error",
            output,
        )

        return success

    except Exception as error:
        update_operation_step(
            operation_id,
            step_index,
            "error",
            str(error),
        )

        return False


def provision_site_live(data: dict, operation_id: str) -> None:
    project_dir = HOST_OPT_DIR / data["project_name"]
    compose_path = project_dir / "docker-compose.prod.yml"
    nginx_path = NGINX_CONFIG_DIR / f"{data['domain']}.conf"

    try:
        if not run_live_step(
            operation_id,
            "Création du dossier projet",
            lambda: (
                project_dir.mkdir(parents=True, exist_ok=True) is None,
                str(project_dir),
            ),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Création du docker-compose",
            lambda: (
                compose_path.write_text(
                    generate_docker_compose(data),
                    encoding="utf-8",
                ) > 0,
                str(compose_path),
            ),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Création du vhost HTTP",
            lambda: (
                nginx_path.write_text(
                    generate_nginx_vhost(data),
                    encoding="utf-8",
                ) > 0,
                str(nginx_path),
            ),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Test Nginx HTTP",
            nginx_test,
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Reload Nginx HTTP",
            nginx_reload,
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Création du certificat SSL",
            lambda: run_certbot_certonly(data),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Création du vhost HTTPS",
            lambda: (
                nginx_path.write_text(
                    generate_nginx_https_vhost(data),
                    encoding="utf-8",
                ) > 0,
                str(nginx_path),
            ),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Test Nginx HTTPS",
            nginx_test,
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Reload Nginx HTTPS",
            nginx_reload,
        ):
            finish_operation(operation_id, False)
            return

        finish_operation(operation_id, True)

    except Exception as error:
        step_index = start_operation_step(
            operation_id,
            "Erreur provisionnement",
            "Une erreur inattendue est survenue.",
        )

        update_operation_step(
            operation_id,
            step_index,
            "error",
            str(error),
        )

        finish_operation(operation_id, False)


def delete_site_live(filename: str, operation_id: str) -> None:
    try:
        vhost = get_vhost_detail(filename)

        if vhost is None:
            step_index = start_operation_step(
                operation_id,
                "Recherche du vhost",
                "Vhost introuvable.",
            )
            update_operation_step(
                operation_id,
                step_index,
                "error",
                "Le vhost demandé est introuvable.",
            )
            finish_operation(operation_id, False)
            return

        container_name = vhost.get("container_name")

        if container_name in PROTECTED_CONTAINERS:
            step_index = start_operation_step(
                operation_id,
                "Protection suppression",
                f"Le conteneur {container_name} est protégé.",
            )
            update_operation_step(
                operation_id,
                step_index,
                "error",
                f"Le conteneur {container_name} est protégé.",
            )
            finish_operation(operation_id, False)
            return

        conf_path = Path(vhost["path"])

        if not run_live_step(
            operation_id,
            "Suppression du fichier vhost",
            lambda: (
                conf_path.unlink() is None,
                str(conf_path),
            ),
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Test Nginx",
            nginx_test,
        ):
            finish_operation(operation_id, False)
            return

        if not run_live_step(
            operation_id,
            "Reload Nginx",
            nginx_reload,
        ):
            finish_operation(operation_id, False)
            return

        finish_operation(operation_id, True)

    except Exception as error:
        step_index = start_operation_step(
            operation_id,
            "Erreur suppression",
            "Une erreur inattendue est survenue.",
        )

        update_operation_step(
            operation_id,
            step_index,
            "error",
            str(error),
        )

        finish_operation(operation_id, False)