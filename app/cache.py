import json
import redis

CACHE_PREFIX = "analysis_cache:"
_client = None


def _get_client():
    global _client
    if _client is None:
        from app.config import Config
        _client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            password=Config.REDIS_PASSWORD,
            decode_responses=True,
        )
    return _client


def get_cached(key: str):
    return _get_client().get(f"{CACHE_PREFIX}{key}")


def set_cached(key: str, value: dict, ttl: int) -> None:
    _get_client().setex(f"{CACHE_PREFIX}{key}", ttl, json.dumps(value))


def ping() -> bool:
    try:
        return bool(_get_client().ping())
    except Exception:
        return False
