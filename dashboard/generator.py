import os
import re
import socket
import subprocess
import time
import docker

from docker.errors import APIError, NotFound
from pathlib import Path


NGINX_CONFIG_DIR = Path(
    os.getenv(
        "ADMINNGINX_NGINX_CONFIG_DIR",
        "/data/nginx-config",
    )
)

HOST_OPT_DIR = Path(
    os.getenv(
        "ADMINNGINX_HOST_OPT_DIR",
        "/host/opt",
    )
)

LETSENCRYPT_DIR = Path(
    os.getenv(
        "ADMINNGINX_LETSENCRYPT_DIR",
        "/data/letsencrypt",
    )
)

NGINX_PROXY_CONTAINER = os.getenv(
    "ADMINNGINX_NGINX_CONTAINER",
    "nginx_proxy",
)

APPLICATION_NETWORK = "internal_network"
APPLICATION_START_TIMEOUT = int(
    os.getenv("ADMINNGINX_APPLICATION_START_TIMEOUT", "30")
)


def explain_compose_failure(
    output: str,
    data: dict,
    returncode: int,
) -> str:
    normalized = output.lower()
    image_name = data["ghcr_image"]
    container_name = data["container_name"]

    if any(
        marker in normalized
        for marker in (
            "denied",
            "unauthorized",
            "authentication required",
            "requested access to the resource is denied",
        )
    ):
        return (
            f"GHCR refuse l'accès à l'image {image_name}.\n\n"
            "Causes probables :\n"
            "- le workflow GitHub Actions n'a pas encore publié l'image ;\n"
            "- le package GHCR est privé ;\n"
            "- le dossier d'authentification Docker de l'hôte n'est pas "
            "monté dans adminnginx ;\n"
            "- le compte ou le jeton utilisé n'a pas le droit read:packages.\n\n"
            "Si « docker pull » fonctionne sur l'hôte mais échoue ici, "
            "définissez DOCKER_CONFIG_PATH dans /opt/adminnginx/.env avec "
            "le chemin du dossier .docker de l'utilisateur authentifié, puis "
            "recréez adminnginx. Ce dossier est monté en lecture seule dans "
            "/root/.docker.\n\n"
            f"Sortie Docker Compose :\n{output}"
        )

    if any(
        marker in normalized
        for marker in (
            "manifest unknown",
            "not found",
            "no such image",
        )
    ):
        return (
            f"L'image {image_name} ou son tag « latest » est introuvable sur "
            "GHCR. Vérifiez le propriétaire, le nom du dépôt et la réussite "
            "du workflow GitHub Actions.\n\n"
            f"Sortie Docker Compose :\n{output}"
        )

    if "network" in normalized and (
        "not found" in normalized or "declared as external" in normalized
    ):
        return (
            f"Un réseau Docker externe requis est introuvable. Créez "
            f"{APPLICATION_NETWORK} avant de relancer le provisionnement :\n"
            f"docker network create {APPLICATION_NETWORK}\n\n"
            f"Sortie Docker Compose :\n{output}"
        )

    if "volume" in normalized and (
        "not found" in normalized or "declared as external" in normalized
    ):
        return (
            "Un volume Docker externe requis est introuvable. Si les médias "
            "sont activés, créez-le avec :\n"
            "docker volume create webapps_media\n\n"
            f"Sortie Docker Compose :\n{output}"
        )

    if (
        "already in use by container" in normalized
        or "container name" in normalized
        and "already in use" in normalized
    ):
        return (
            f"Le nom de conteneur {container_name} est déjà utilisé par un "
            "autre projet. Supprimez le conflit ou choisissez un autre nom.\n\n"
            f"Sortie Docker Compose :\n{output}"
        )

    return (
        f"Échec de docker compose up (code {returncode}).\n"
        f"{output or 'Aucune sortie Docker.'}\n\n"
        "Vérifiez l'image GHCR, les volumes et réseaux externes, puis les "
        f"éventuels conflits autour du conteneur {container_name}."
    )


def build_server_names(domain: str, include_www: bool) -> str:
    if include_www:
        return f"{domain} www.{domain}"
    return domain


def generate_media_location(data: dict) -> str:
    if not data.get("enable_media", False):
        return ""

    return """
    location /media/ {
        alias /srv/webapps-media/;
        autoindex off;
    }
"""


def generate_docker_compose(data: dict) -> str:
    media_service = ""
    media_volume = ""
    env_file = ""

    if data.get("has_env_file", False):
        env_file = """    env_file:
      - .env
"""

    if data.get("enable_media", False):
        media_service = """    volumes:
      - webapps_media:/app/media
"""
        media_volume = """
volumes:
  webapps_media:
    external: true
"""

    return f"""services:
  {data["project_name"]}:
    image: {data["ghcr_image"]}
    container_name: {data["container_name"]}
    restart: unless-stopped
{env_file}\
{media_service}\
    networks:
      - internal_network
    expose:
      - "{data["internal_port"]}"

networks:
  internal_network:
    external: true
{media_volume}"""


def run_application_compose(
    compose_path: Path,
    data: dict,
) -> tuple[bool, str]:
    """Run the generated Compose project through the mounted Docker socket."""
    try:
        if not compose_path.is_file():
            return (
                False,
                f"Fichier Compose introuvable : {compose_path}",
            )

        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(compose_path.parent),
                "-f",
                str(compose_path),
                "up",
                "-d",
                "--pull",
                "always",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part.strip()
        )

        if result.returncode != 0:
            return (
                False,
                explain_compose_failure(
                    output,
                    data,
                    result.returncode,
                ),
            )

        return True, output or (
            f"Projet Compose démarré : {data['container_name']}"
        )

    except FileNotFoundError:
        return (
            False,
            "La commande « docker compose » est absente du conteneur "
            "adminnginx. Reconstruisez l'image avec le Dockerfile actuel.",
        )
    except subprocess.TimeoutExpired as error:
        output = "\n".join(
            part.strip()
            for part in (error.stdout, error.stderr)
            if part
        )
        return (
            False,
            "Le démarrage Docker Compose a dépassé 300 secondes.\n"
            f"{output or 'Aucune sortie Docker.'}",
        )
    except Exception as error:
        return (
            False,
            f"Erreur inattendue pendant docker compose up : {error}",
        )


def verify_application_container(data: dict) -> tuple[bool, str]:
    """Check the state and shared network required for Nginx DNS."""
    container_name = data["container_name"]

    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        container.reload()

        if container.status != "running":
            logs = container.logs(
                stdout=True,
                stderr=True,
                tail=50,
            ).decode("utf-8", errors="ignore")
            return (
                False,
                f"Le conteneur {container_name} n'est pas actif "
                f"(état : {container.status}).\n"
                f"Derniers logs :\n{logs or 'Aucun log disponible.'}",
            )

        networks = container.attrs.get("NetworkSettings", {}).get(
            "Networks",
            {},
        )
        if APPLICATION_NETWORK not in networks:
            return (
                False,
                f"Le conteneur {container_name} n'est pas connecté au réseau "
                f"{APPLICATION_NETWORK}. Nginx ne pourra pas résoudre son nom.",
            )

        deadline = time.monotonic() + APPLICATION_START_TIMEOUT
        last_connection_error = ""

        while time.monotonic() <= deadline:
            container.reload()
            if container.status != "running":
                logs = container.logs(
                    stdout=True,
                    stderr=True,
                    tail=50,
                ).decode("utf-8", errors="ignore")
                return (
                    False,
                    f"Le conteneur {container_name} s'est arrêté pendant son "
                    f"démarrage (état : {container.status}).\n"
                    f"Derniers logs :\n{logs or 'Aucun log disponible.'}",
                )

            try:
                with socket.create_connection(
                    (container_name, data["internal_port"]),
                    timeout=2,
                ):
                    break
            except OSError as error:
                last_connection_error = str(error)
                time.sleep(1)
        else:
            logs = container.logs(
                stdout=True,
                stderr=True,
                tail=50,
            ).decode("utf-8", errors="ignore")
            exposed_ports = sorted(
                (
                    container.attrs.get("Config", {})
                    .get("ExposedPorts", {})
                    .keys()
                )
            )
            exposed_hint = ""
            if exposed_ports:
                exposed_hint = (
                    "\nPorts déclarés par l'image : "
                    f"{', '.join(exposed_ports)}."
                )
            return (
                False,
                f"Le conteneur {container_name} est actif, mais son port "
                f"{data['internal_port']} ne répond pas après "
                f"{APPLICATION_START_TIMEOUT} secondes. Vérifiez le port "
                "interne saisi et la commande de démarrage de l'image.\n"
                f"Dernière erreur réseau : {last_connection_error}\n"
                f"{exposed_hint}\n"
                f"Derniers logs :\n{logs or 'Aucun log disponible.'}",
            )

        network_ip = networks[APPLICATION_NETWORK].get(
            "IPAddress",
            "adresse non disponible",
        )
        return (
            True,
            f"Conteneur {container_name} actif sur {APPLICATION_NETWORK} "
            f"({network_ip}), accessible par Nginx sur le port "
            f"{data['internal_port']}.",
        )

    except NotFound:
        return (
            False,
            f"Le conteneur {container_name} est introuvable après sa création.",
        )
    except APIError as error:
        return (
            False,
            f"Impossible de vérifier le conteneur {container_name}.\n"
            f"Détail Docker : {error}",
        )
    except Exception as error:
        return (
            False,
            f"Erreur inattendue pendant la vérification de {container_name} : "
            f"{error}",
        )


def generate_nginx_vhost(data: dict) -> str:
    server_names = build_server_names(
        data["domain"],
        data["include_www"],
    )
    media_location = generate_media_location(data)

    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_names};

    location /.well-known/acme-challenge/ {{
        root /usr/share/nginx/html;
    }}
{media_location}

    location / {{
        proxy_pass http://{data["container_name"]}:{data["internal_port"]};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""


def generate_nginx_https_vhost(data: dict) -> str:
    server_names = build_server_names(
        data["domain"],
        data["include_www"],
    )
    media_location = generate_media_location(data)

    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_names};

    location /.well-known/acme-challenge/ {{
        root /usr/share/nginx/html;
    }}

    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {server_names};

    ssl_certificate /etc/letsencrypt/live/{data["domain"]}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{data["domain"]}/privkey.pem;
{media_location}

    location / {{
        proxy_pass http://{data["container_name"]}:{data["internal_port"]};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }}
}}
"""


def extract_server_names(content: str) -> list[str]:
    matches = re.findall(r"server_name\s+([^;]+);", content)
    domains = []

    for match in matches:
        for domain in match.split():
            if domain not in domains:
                domains.append(domain)

    return domains


def extract_proxy_container(content: str) -> str | None:
    match = re.search(
        r"proxy_pass\s+http://([a-zA-Z0-9_.-]+)(?::\d+)?",
        content,
    )

    if not match:
        return None

    return match.group(1)


def list_vhosts() -> list[dict]:
    vhosts = []

    if not NGINX_CONFIG_DIR.exists():
        return vhosts

    for conf_file in sorted(NGINX_CONFIG_DIR.glob("*.conf")):
        content = conf_file.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        domains = extract_server_names(content)

        vhosts.append(
            {
                "file": conf_file.name,
                "path": str(conf_file),
                "domains": domains,
                "primary_domain": domains[0] if domains else "Non détecté",
                "container_name": extract_proxy_container(content),
            }
        )

    return vhosts


def get_vhost_detail(filename: str) -> dict | None:
    safe_filename = Path(filename).name

    if not safe_filename.endswith(".conf"):
        return None

    conf_path = NGINX_CONFIG_DIR / safe_filename

    if not conf_path.exists():
        return None

    content = conf_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )
    domains = extract_server_names(content)

    return {
        "file": safe_filename,
        "path": str(conf_path),
        "domains": domains,
        "primary_domain": domains[0] if domains else "Non détecté",
        "container_name": extract_proxy_container(content),
        "content": content,
    }


def update_vhost_file(filename: str, content: str) -> bool:
    safe_filename = Path(filename).name

    if not safe_filename.endswith(".conf"):
        return False

    conf_path = NGINX_CONFIG_DIR / safe_filename

    if not conf_path.exists():
        return False

    conf_path.write_text(content, encoding="utf-8")

    return True


def list_ssl_certificates() -> list[dict]:
    certs = []

    live_dir = LETSENCRYPT_DIR / "live"

    if not live_dir.exists():
        return certs

    for cert_dir in sorted(live_dir.iterdir()):
        if not cert_dir.is_dir():
            continue

        if cert_dir.name == "README":
            continue

        fullchain = cert_dir / "fullchain.pem"
        privkey = cert_dir / "privkey.pem"

        certs.append(
            {
                "domain": cert_dir.name,
                "fullchain_exists": fullchain.exists(),
                "privkey_exists": privkey.exists(),
            }
        )

    return certs


def get_dashboard_summary() -> dict:
    vhosts = list_vhosts()
    certs = list_ssl_certificates()

    return {
        "vhosts_count": len(vhosts),
        "certificates_count": len(certs),
        "recent_vhosts": vhosts[:5],
        "certificates": certs,
    }


def run_nginx_command(command: list[str]) -> tuple[bool, str]:
    try:
        client = docker.from_env()
        container = client.containers.get(NGINX_PROXY_CONTAINER)

        result = container.exec_run(
            command,
            stdout=True,
            stderr=True,
        )

        output = result.output.decode("utf-8", errors="ignore")

        return result.exit_code == 0, output

    except Exception as error:
        return False, str(error)


def nginx_test() -> tuple[bool, str]:
    return run_nginx_command(["nginx", "-t"])


def nginx_reload() -> tuple[bool, str]:
    return run_nginx_command(["nginx", "-s", "reload"])


def run_certbot_certonly(data: dict) -> tuple[bool, str]:
    try:
        client = docker.from_env()

        command = [
            "certonly",
            "--webroot",
            "-w",
            "/usr/share/nginx/html",
            "-d",
            data["domain"],
            "--email",
            data["certbot_email"],
            "--agree-tos",
            "--no-eff-email",
            "--non-interactive",
        ]

        if data["include_www"]:
            command.extend(["-d", f"www.{data['domain']}"])

        output = client.containers.run(
            "certbot/certbot",
            command=command,
            remove=True,
            volumes={
                "/opt/nginx_proxy/letsencrypt": {
                    "bind": "/etc/letsencrypt",
                    "mode": "rw",
                },
                "/opt/nginx_proxy/html": {
                    "bind": "/usr/share/nginx/html",
                    "mode": "rw",
                },
            },
            detach=False,
        )

        return True, output.decode("utf-8", errors="ignore")

    except Exception as error:
        return False, str(error)
