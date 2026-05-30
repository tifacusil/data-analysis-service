import requests


def register() -> None:
    """Register the service with Consul via HTTP API."""
    pass


def deregister() -> None:
    """Deregister the service from Consul via HTTP API."""
    pass


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
