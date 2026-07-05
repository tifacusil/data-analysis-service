import requests


def register() -> None:
    """Register the service with Consul via HTTP API."""
    from app.config import Config

    try:
        headers: dict[str, str] = {}
        if Config.CONSUL_TOKEN:
            headers["X-Consul-Token"] = Config.CONSUL_TOKEN

        url = f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}/v1/agent/service/register"

        bind_host = (Config.HOST or "").strip()
        check_host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
        if not check_host:
            check_host = "127.0.0.1"

        check_port = int(Config.PORT)
        prefix = (Config.ROUTE_PREFIX or "").strip()
        if prefix and not prefix.startswith("/"):
            prefix = f"/{prefix}"
        prefix = prefix.rstrip("/")
        check_path = f"{prefix}/health" if prefix else "/analysis/health"
        check_url = f"http://{check_host}:{check_port}{check_path}"

        payload = {
            "ID": Config.INSTANCE_ID,
            "Name": "data-analysis",
            "Address": check_host,
            "Port": int(Config.PORT),
            "Tags": [
                f"version:{Config.VERSION}",
                "lang-python",
                f"env:{Config.ENV}",
            ],
            "Check": {
                "HTTP": check_url,
                "Method": "GET",
                "Interval": "10s",
                "Timeout": "2s",
                "DeregisterCriticalServiceAfter": "1m",
            },
        }

        requests.put(url, json=payload, headers=headers, timeout=3).raise_for_status()
    except Exception:
        return


def deregister() -> None:
    """Deregister the service from Consul via HTTP API."""
    from app.config import Config

    try:
        headers: dict[str, str] = {}
        if Config.CONSUL_TOKEN:
            headers["X-Consul-Token"] = Config.CONSUL_TOKEN

        url = (
            f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}"
            f"/v1/agent/service/deregister/{Config.INSTANCE_ID}"
        )
        requests.put(url, headers=headers, timeout=3)
    except Exception:
        return


def is_registered() -> bool:
    """Return True if the service is currently registered in Consul."""
    from app.config import Config
    try:
        headers = {}
        if Config.CONSUL_TOKEN:
            headers["X-Consul-Token"] = Config.CONSUL_TOKEN
        url = (
            f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}"
            f"/v1/agent/service/{Config.INSTANCE_ID}"
        )
        resp = requests.get(url, headers=headers, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False
