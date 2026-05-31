from flask import request
try:
    from flask_smorest import Blueprint  # type: ignore
except ModuleNotFoundError:
    from flask import Blueprint
from app import cache
from app.config import Config
from services import predict_service

blp = Blueprint("predict", __name__, url_prefix="/analysis")


_ALLOWED_MODELS = {"arima", "gm11"}


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

    horizon_raw = raw.get("horizon")
    try:
        horizon = int(horizon_raw)
    except Exception:
        errors["horizon"] = ["Debe ser un entero."]
        horizon = 0
    if horizon <= 0:
        errors["horizon"] = ['Debe ser un entero > 0.']

    arima_order_raw = raw.get("arima_order", None)
    arima_order = None
    if arima_order_raw is not None:
        if not isinstance(arima_order_raw, list) or len(arima_order_raw) != 3:
            errors["arima_order"] = ['Debe ser una lista de 3 enteros: [p, d, q].']
        else:
            try:
                arima_order = [int(x) for x in arima_order_raw]
            except Exception:
                errors["arima_order"] = ["Debe contener enteros."]

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
        "horizon": horizon,
        "arima_order": arima_order,
    }
    return data, None


@blp.route("/predict", methods=["POST"])
def post_predict():
    data, errors = _load_request()
    if errors:
        return {"error": "validation_error", "message": errors}, 400

    try:
        cache_key = cache.make_analysis_cache_key(data)
        cached = cache.get_cached_json(cache_key)
        if cached is not None:
            return cached, 200

        result = predict_service.predict(
            data["values"],
            data["timestamps"],
            data["model"],
            data["horizon"],
            data.get("arima_order"),
        )
        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
        return result, 200
    except ValueError as err:
        return {"error": "validation_error", "message": str(err)}, 400
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Prediction not yet implemented (Card 4B2)",
        }, 501
