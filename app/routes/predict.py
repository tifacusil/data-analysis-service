import hashlib
import json

import pandas as pd
from flask import request, current_app
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError

from app import cache
from app.config import Config
from services import predict_service

blp = Blueprint("predict", __name__, url_prefix="/analysis")


class PredictRequestSchema(Schema):
    values = fields.List(fields.Float(), required=True)
    timestamps = fields.List(fields.String(), required=True)
    model = fields.String(
        required=True,
        validate=validate.OneOf(["arima", "gm11"]),
    )
    horizon = fields.Integer(required=True)
    arima_order = fields.List(fields.Integer(), load_default=None)


@blp.route("/predict", methods=["POST"])
def post_predict():
    schema = PredictRequestSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return {"error": "validation_error", "message": err.messages}, 400

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
