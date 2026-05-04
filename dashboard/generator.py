import os
import re

from pathlib import Path
from django.conf import settings


NGINX_CONFIG_DIR = Path(
    os.getenv(
        "ADMINNGINX_NGINX_CONFIG_DIR",
        "/data/nginx-config"
    )
)

HOST_OPT_DIR = Path(
    os.getenv(
        "ADMINNGINX_HOST_OPT_DIR",
        "/host/opt"
    )
)

def build_server_names(domain: str, include_www: bool) -> str:
    if include_www:
        return f"{domain} www.{domain}"
    return domain


def generate_docker_compose(data: dict) -> str:
    return f"""services:
  {data["project_name"]}:
    image: {data["ghcr_image"]}
    container_name: {data["container_name"]}
    restart: unless-stopped
    networks:
      - internal_network
    expose:
      - "{data["internal_port"]}"

networks:
  internal_network:
    external: true
"""


def generate_nginx_vhost(data: dict) -> str:
    server_names = build_server_names(
        data["domain"],
        data["include_www"]
    )

    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {server_names};

    location /.well-known/acme-challenge/ {{
        root /usr/share/nginx/html;
    }}

    location / {{
        proxy_pass http://{data["container_name"]}:{data["internal_port"]};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""


def write_project_files(data: dict) -> dict:
    project_dir = HOST_OPT_DIR / data["project_name"]
    project_dir.mkdir(parents=True, exist_ok=True)

    compose_path = project_dir / "docker-compose.prod.yml"
    compose_path.write_text(
        generate_docker_compose(data),
        encoding="utf-8"
    )

    nginx_path = NGINX_CONFIG_DIR / f"{data['domain']}.conf"
    nginx_path.write_text(
        generate_nginx_vhost(data),
        encoding="utf-8"
    )

    return {
        "project_dir": str(project_dir),
        "compose_path": str(compose_path),
        "nginx_path": str(nginx_path),
    }

def generate_commands(data: dict) -> list[str]:
    domain_args = f"-d {data['domain']}"

    if data["include_www"]:
        domain_args += f" -d www.{data['domain']}"

    return [
        f"cd {data['server_path']}",
        "docker compose -f docker-compose.prod.yml pull",
        "docker compose -f docker-compose.prod.yml up -d",
        (
            "docker run --rm "
            "-v /opt/nginx_proxy/letsencrypt:/etc/letsencrypt "
            "-v /opt/nginx_proxy/html:/usr/share/nginx/html "
            "certbot/certbot certonly "
            "--webroot -w /usr/share/nginx/html "
            f"{domain_args} "
            f"--email {data['certbot_email']} "
            "--agree-tos --no-eff-email"
        ),
        "docker exec nginx_proxy nginx -t",
        "docker exec nginx_proxy nginx -s reload",
        (
            "docker run --rm "
            "-v /opt/nginx_proxy/letsencrypt:/etc/letsencrypt "
            "-v /opt/nginx_proxy/html:/usr/share/nginx/html "
            "certbot/certbot renew "
            "--webroot -w /usr/share/nginx/html "
            "--dry-run"
        ),
        f"curl -4 -I http://{data['domain']}",
        f"curl -4 -I https://{data['domain']}",
        f"curl -6 -I https://{data['domain']}",
    ]

def extract_server_names(content: str) -> list[str]:
    matches = re.findall(r"server_name\s+([^;]+);", content)
    domains = []

    for match in matches:
        for domain in match.split():
            if domain not in domains:
                domains.append(domain)

    return domains


def list_vhosts() -> list[dict]:
    vhosts = []

    if not NGINX_CONFIG_DIR.exists():
        return vhosts

    for conf_file in sorted(NGINX_CONFIG_DIR.glob("*.conf")):
        content = conf_file.read_text(encoding="utf-8")
        domains = extract_server_names(content)

        vhosts.append(
            {
                "file": conf_file.name,
                "path": str(conf_file),
                "domains": domains,
                "primary_domain": domains[0] if domains else "Non détecté",
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

    content = conf_path.read_text(encoding="utf-8")
    domains = extract_server_names(content)

    return {
        "file": safe_filename,
        "path": str(conf_path),
        "domains": domains,
        "primary_domain": domains[0] if domains else "Non détecté",
        "content": content,
    }

def list_ssl_certificates() -> list[dict]:
    certs = []

    letsencrypt_dir = Path(
        os.getenv(
            "ADMINNGINX_LETSENCRYPT_DIR",
            "/data/letsencrypt"
        )
    )

    live_dir = letsencrypt_dir / "live"

    if not live_dir.exists():
        return certs

    for cert_dir in sorted(live_dir.iterdir()):
        if not cert_dir.is_dir():
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

def update_vhost_file(filename: str, content: str) -> bool:
    safe_filename = Path(filename).name

    if not safe_filename.endswith(".conf"):
        return False

    conf_path = NGINX_CONFIG_DIR / safe_filename

    if not conf_path.exists():
        return False

    conf_path.write_text(content, encoding="utf-8")

    return True