from flask import request
try:
    from flask_smorest import Blueprint  # type: ignore
except ModuleNotFoundError:
    from flask import Blueprint
from app import cache
from app.config import Config
from services import outliers_service

blp = Blueprint("outliers", __name__, url_prefix="/analysis")


_ALLOWED_METHODS = {"3sigma", "chauvenet", "iqr"}


def _load_request() -> tuple[dict, dict | None]:
    raw = request.get_json(silent=True) or {}
    errors: dict = {}

    values = raw.get("values")
    if not isinstance(values, list) or len(values) == 0:
        errors["values"] = ["Debe ser una lista no vacía."]
    timestamps = raw.get("timestamps")
    if not isinstance(timestamps, list) or len(timestamps) == 0:
        errors["timestamps"] = ["Debe ser una lista no vacía."]
    method = raw.get("method")
    if not isinstance(method, str) or method not in _ALLOWED_METHODS:
        errors["method"] = [f"Debe ser uno de: {sorted(_ALLOWED_METHODS)}."]

    if errors:
        return {}, errors

    try:
        values_f = [float(v) for v in values]
    except Exception:
        return {}, {"values": ["Debe contener números."]}

    data = {"values": values_f, "timestamps": [str(t) for t in timestamps], "method": method}
    return data, None


@blp.route("/outliers", methods=["POST"])
def post_outliers():
    data, errors = _load_request()
    if errors:
        return {"error": "validation_error", "message": errors}, 400

    try:
        cache_key = cache.make_analysis_cache_key(data)
        cached = cache.get_cached_json(cache_key)
        if cached is not None:
            return cached, 200

        result = outliers_service.detect_outliers(
            data["values"], data["timestamps"], data["method"]
        )
        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
        return result, 200
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Outlier detection not yet implemented (Card 4A1)",
        }, 501
