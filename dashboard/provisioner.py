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


PROTECTED_CONTAINERS = {
    "adminnginx",
    "nginx_proxy",
    "certbot",
}


def add_step(
    steps: list[dict],
    name: str,
    success: bool,
    message: str = "",
) -> None:
    steps.append(
        {
            "name": name,
            "success": success,
            "message": message,
        }
    )


def provision_site(data: dict) -> dict:
    steps = []

    project_dir = HOST_OPT_DIR / data["project_name"]
    compose_path = project_dir / "docker-compose.prod.yml"
    nginx_path = NGINX_CONFIG_DIR / f"{data['domain']}.conf"

    try:
        # 1. Création du dossier projet
        project_dir.mkdir(parents=True, exist_ok=True)
        add_step(
            steps,
            "Création du dossier projet",
            True,
            str(project_dir),
        )

        # 2. Création du docker-compose du site
        compose_path.write_text(
            generate_docker_compose(data),
            encoding="utf-8",
        )
        add_step(
            steps,
            "Création du docker-compose",
            True,
            str(compose_path),
        )

        # 3. Création du vhost HTTP temporaire
        nginx_path.write_text(
            generate_nginx_vhost(data),
            encoding="utf-8",
        )
        add_step(
            steps,
            "Création du vhost HTTP",
            True,
            str(nginx_path),
        )

        # 4. Test Nginx HTTP
        success, output = nginx_test()
        add_step(
            steps,
            "Test Nginx HTTP",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        # 5. Reload Nginx HTTP
        success, output = nginx_reload()
        add_step(
            steps,
            "Reload Nginx HTTP",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        # 6. Création du certificat SSL via Certbot
        success, output = run_certbot_certonly(data)
        add_step(
            steps,
            "Création du certificat SSL",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        # 7. Remplacement par le vhost HTTPS définitif
        nginx_path.write_text(
            generate_nginx_https_vhost(data),
            encoding="utf-8",
        )
        add_step(
            steps,
            "Création du vhost HTTPS",
            True,
            str(nginx_path),
        )

        # 8. Test Nginx HTTPS
        success, output = nginx_test()
        add_step(
            steps,
            "Test Nginx HTTPS",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        # 9. Reload Nginx HTTPS
        success, output = nginx_reload()
        add_step(
            steps,
            "Reload Nginx HTTPS",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        return {
            "success": True,
            "steps": steps,
        }

    except Exception as error:
        add_step(
            steps,
            "Erreur provisionnement",
            False,
            str(error),
        )

        return {
            "success": False,
            "steps": steps,
        }


def delete_site(filename: str) -> dict:
    steps = []

    vhost = get_vhost_detail(filename)

    if vhost is None:
        add_step(
            steps,
            "Recherche du vhost",
            False,
            "Vhost introuvable.",
        )

        return {
            "success": False,
            "steps": steps,
        }

    container_name = vhost.get("container_name")

    if container_name in PROTECTED_CONTAINERS:
        add_step(
            steps,
            "Protection suppression",
            False,
            f"Le conteneur {container_name} est protégé.",
        )

        return {
            "success": False,
            "steps": steps,
        }

    conf_path = Path(vhost["path"])

    try:
        conf_path.unlink()
        add_step(
            steps,
            "Suppression du fichier vhost",
            True,
            str(conf_path),
        )

        success, output = nginx_test()
        add_step(
            steps,
            "Test Nginx",
            success,
            output,
        )

        if not success:
            return {
                "success": False,
                "steps": steps,
            }

        success, output = nginx_reload()
        add_step(
            steps,
            "Reload Nginx",
            success,
            output,
        )

        return {
            "success": success,
            "steps": steps,
        }

    except Exception as error:
        add_step(
            steps,
            "Erreur suppression",
            False,
            str(error),
        )

        return {
            "success": False,
            "steps": steps,
        }