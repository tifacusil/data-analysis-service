try:
    from flask_smorest import Blueprint  # type: ignore
    from marshmallow import Schema, fields, validate
    _HAS_OPENAPI = True
except ModuleNotFoundError:
    from flask import Blueprint
    _HAS_OPENAPI = False
import hashlib
import json

import pandas as pd
from flask import request, current_app

from app import cache
from app.config import Config
from services import predict_service

blp = Blueprint("predict", __name__, url_prefix="/analysis")


_ALLOWED_MODELS = {"arima", "gm11"}

if _HAS_OPENAPI:
    class PredictRequestSchema(Schema):
        values = fields.List(
            fields.Float(),
            required=True,
            metadata={"example": [1.2, 3.4, 2.8, 2.1]},
        )
        timestamps = fields.List(
            fields.String(),
            required=True,
            metadata={
                "example": [
                    "2019-06-01T00:00:00Z",
                    "2019-06-02T00:00:00Z",
                    "2019-06-03T00:00:00Z",
                    "2019-06-04T00:00:00Z",
                ]
            },
        )
        model = fields.String(
            required=True,
            validate=validate.OneOf(sorted(_ALLOWED_MODELS)),
            metadata={"example": "arima"},
        )
        horizon = fields.Integer(required=True, metadata={"example": 30})
        arima_order = fields.List(
            fields.Integer(),
            load_default=None,
            validate=validate.Length(equal=3),
            metadata={"example": [1, 1, 1]},
        )


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


def _handle_predict(data):
    values = data["values"]
    timestamps = data["timestamps"]
    model = data["model"]
    horizon = data["horizon"]
    arima_order = data["arima_order"]

    if len(values) < 4:
        return {"error": "validation_error", "message": "values must have at least 4 elements"}, 400

    if len(values) != len(timestamps):
        return {"error": "validation_error", "message": "timestamps and values must have the same length"}, 400

    if horizon < 1 or horizon > 365:
        return {"error": "validation_error", "message": "horizon must be between 1 and 365"}, 400

    try:
        pd.to_datetime(timestamps, utc=True)
    except Exception:
        return {"error": "validation_error", "message": "timestamps contains invalid ISO-8601 dates"}, 400

    if arima_order is not None:
        if len(arima_order) != 3 or any(v < 0 for v in arima_order):
            return {
                "error": "validation_error",
                "message": "arima_order must be a list of 3 non-negative integers",
            }, 400

    order = tuple(arima_order) if arima_order is not None else (1, 1, 1)

    body = request.get_json(silent=True) or {}
    cache_key = f"predict:{hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}"

    try:
        cached = cache.get_cached(cache_key)
        if cached:
            return json.loads(cached), 200, {"X-Cache": "HIT"}
    except Exception:
        current_app.logger.warning("Redis unavailable, skipping cache lookup")

    try:
        if model == "arima":
            result = predict_service.arima_predict(values, timestamps, horizon, order)
        else:
            result = predict_service.gm11_predict(values, timestamps, horizon)
    except ValueError as err:
        return {"error": "validation_error", "message": str(err)}, 400
    except Exception:
        current_app.logger.exception("Unexpected error in predict endpoint")
        return {"error": "internal_error", "message": "An unexpected error occurred"}, 500

    try:
        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
    except Exception:
        current_app.logger.warning("Redis unavailable, skipping cache write")

    return result, 200, {"X-Cache": "MISS"}


if _HAS_OPENAPI:
    @blp.route("/predict", methods=["POST"])
    @blp.arguments(PredictRequestSchema, location="json")
    def post_predict(data):
        return _handle_predict(data)
else:
    @blp.route("/predict", methods=["POST"])
    def post_predict():
        data, errors = _load_request()
        if errors:
            return {"error": "validation_error", "message": errors}, 400
        return _handle_predict(data)
