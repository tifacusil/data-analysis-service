import hashlib
import json
from typing import Any, Mapping

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
    try:
        _get_client().setex(f"{CACHE_PREFIX}{key}", ttl, json.dumps(value))
    except Exception:
        return


def make_analysis_cache_key(body: Mapping[str, Any]) -> str:
    normalized = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"analysis:{digest}"


def get_cached_json(key: str) -> dict | None:
    try:
        raw = get_cached(key)
    except Exception:
        return None
    if not isinstance(raw, str) or not raw:
        return None
    try:
        value = json.loads(raw)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def ping() -> bool:
    try:
        return bool(_get_client().ping())
    except Exception:
        return False
