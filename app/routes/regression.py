from flask import request
try:
    from flask_smorest import Blueprint  # type: ignore
except ModuleNotFoundError:
    from flask import Blueprint
from app import cache
from app.config import Config
from services import regression_service

blp = Blueprint("regression", __name__, url_prefix="/analysis")


_ALLOWED_MODELS = {"polynomial", "bayesian"}


def _load_request() -> tuple[dict, dict | None]:
    raw = request.get_json(silent=True) or {}
    errors: dict = {}

    values = raw.get("values")
    if not isinstance(values, list) or len(values) == 0:
        errors["values"] = ["Debe ser una lista no vacía."]
    timestamps = raw.get("timestamps")
    if not isinstance(timestamps, list) or len(timestamps) == 0:
        errors["timestamps"] = ["Debe ser una lista no vacía."]
    model = raw.get("model")
    if not isinstance(model, str) or model not in _ALLOWED_MODELS:
        errors["model"] = [f"Debe ser uno de: {sorted(_ALLOWED_MODELS)}."]

    degree_raw = raw.get("degree", 3)
    try:
        degree = int(degree_raw)
    except Exception:
        errors["degree"] = ["Debe ser un entero."]
        degree = 3
    if degree <= 0:
        errors["degree"] = ['Debe ser un entero > 0.']

    if errors:
        return {}, errors

    try:
        values_f = [float(v) for v in values]
    except Exception:
        return {}, {"values": ["Debe contener números."]}

    data = {
        "values": values_f,
        "timestamps": [str(t) for t in timestamps],
        "model": model,
        "degree": degree,
    }
    return data, None


@blp.route("/regression", methods=["POST"])
def post_regression():
    data, errors = _load_request()
    if errors:
        return {"error": "validation_error", "message": errors}, 400

    try:
        cache_key = cache.make_analysis_cache_key(data)
        cached = cache.get_cached_json(cache_key)
        if cached is not None:
            return cached, 200

        result = regression_service.fit_regression(
            data["values"],
            data["timestamps"],
            data["model"],
            data.get("degree", 3),
        )
        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
        return result, 200
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Regression not yet implemented (Card 4B1)",
        }, 501
