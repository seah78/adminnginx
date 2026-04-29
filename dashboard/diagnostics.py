import socket
import ssl
import certifi

from datetime import datetime, timezone

import requests


def check_dns_a(domain: str) -> dict:
    try:
        ip = socket.gethostbyname(domain)

        return {
            "name": "DNS A",
            "status": "success",
            "message": ip,
        }

    except Exception as error:
        return {
            "name": "DNS A",
            "status": "error",
            "message": str(error),
        }


def check_dns_aaaa(domain: str) -> dict:
    try:
        results = socket.getaddrinfo(
            domain,
            None,
            socket.AF_INET6
        )

        ips = sorted({
            item[4][0]
            for item in results
        })

        return {
            "name": "DNS AAAA",
            "status": "success",
            "message": ", ".join(ips) if ips else "Aucune IPv6 trouvée",
        }

    except Exception as error:
        return {
            "name": "DNS AAAA",
            "status": "warning",
            "message": str(error),
        }


def check_http(domain: str) -> dict:
    try:
        response = requests.get(
            f"http://{domain}",
            timeout=5,
            allow_redirects=False,
        )

        return {
            "name": "HTTP",
            "status": "success" if response.status_code < 400 else "warning",
            "message": f"HTTP {response.status_code}",
        }

    except Exception as error:
        return {
            "name": "HTTP",
            "status": "error",
            "message": str(error),
        }


def check_https(domain: str) -> dict:
    try:
        response = requests.get(
            f"https://{domain}",
            timeout=5,
            allow_redirects=False,
        )

        return {
            "name": "HTTPS",
            "status": "success" if response.status_code < 400 else "warning",
            "message": f"HTTP {response.status_code}",
        }

    except Exception as error:
        return {
            "name": "HTTPS",
            "status": "error",
            "message": str(error),
        }


def check_ssl_certificate(domain: str) -> dict:
    try:

        context = ssl.create_default_context(
            cafile=certifi.where()
        )
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        expires_raw = cert["notAfter"]

        expires_at = datetime.strptime(
            expires_raw,
            "%b %d %H:%M:%S %Y %Z"
        ).replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        days_left = (expires_at - now).days

        if days_left > 30:
            status = "success"
        elif days_left > 10:
            status = "warning"
        else:
            status = "error"

        return {
            "name": "Certificat SSL",
            "status": status,
            "message": f"Expire dans {days_left} jour(s)",
        }

    except Exception as error:
        return {
            "name": "Certificat SSL",
            "status": "error",
            "message": str(error),
        }


def run_domain_diagnostics(domain: str) -> list[dict]:
    return [
        check_dns_a(domain),
        check_dns_aaaa(domain),
        check_http(domain),
        check_https(domain),
        check_ssl_certificate(domain),
    ]