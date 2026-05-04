import os
import re
import docker

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
        data["include_www"],
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


def generate_nginx_https_vhost(data: dict) -> str:
    server_names = build_server_names(
        data["domain"],
        data["include_www"],
    )

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