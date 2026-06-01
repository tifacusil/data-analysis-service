import os


class Config:
    PORT = int(os.environ.get("ANALYSIS__PORT", 8090))
    HOST = os.environ.get("ANALYSIS__HOST", "0.0.0.0")
    ENV = os.environ.get("ANALYSIS__ENV", "dev")
    VERSION = os.environ.get("ANALYSIS__VERSION", "1.0.0")
    INSTANCE_ID = os.environ.get("ANALYSIS__INSTANCE_ID", "data-analysis-01")

    ROUTE_PREFIX = (os.environ.get("ANALYSIS__ROUTE_PREFIX", "") or "").strip()
    PUBLIC_URL_PREFIX = (os.environ.get("ANALYSIS__PUBLIC_URL_PREFIX", "") or "").strip()

    REDIS_HOST = os.environ.get("ANALYSIS__REDIS__HOST", "localhost")
    REDIS_PORT = int(os.environ.get("ANALYSIS__REDIS__PORT", 6379))
    REDIS_PASSWORD = os.environ.get("ANALYSIS__REDIS__PASSWORD", "") or None
    REDIS_CACHE_TTL_SECONDS = int(
        os.environ.get("ANALYSIS__REDIS__CACHE_TTL_SECONDS", 3600)
    )

    CONSUL_HOST = os.environ.get("ANALYSIS__CONSUL__HOST", "localhost")
    CONSUL_PORT = int(os.environ.get("ANALYSIS__CONSUL__PORT", 8500))
    CONSUL_TOKEN = os.environ.get("ANALYSIS__CONSUL__TOKEN", "") or None
    CONSUL_HEALTH_PORT = int(
        os.environ.get("ANALYSIS__CONSUL__HEALTH_PORT", 9090)
    )

    # flask-smorest / OpenAPI
    API_TITLE = "Data Analysis Service"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/"
    OPENAPI_SWAGGER_UI_PATH = "/swagger-ui"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    _normalized_prefix = (PUBLIC_URL_PREFIX.rstrip("/") if PUBLIC_URL_PREFIX else "")
    OPENAPI_SWAGGER_UI_CONFIG = {"url": f"{_normalized_prefix}/openapi.json"}
