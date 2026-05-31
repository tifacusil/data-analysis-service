import hashlib
import json

import pandas as pd
from flask import request, current_app
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError

from app import cache
from app.config import Config
from services import regression_service

blp = Blueprint("regression", __name__, url_prefix="/analysis")


class RegressionRequestSchema(Schema):
    values = fields.List(fields.Float(), required=True)
    timestamps = fields.List(fields.String(), required=True)
    model = fields.String(
        required=True,
        validate=validate.OneOf(["polynomial", "bayesian"]),
    )
    degree = fields.Integer(load_default=3)


@blp.route("/regression", methods=["POST"])
def post_regression():
    schema = RegressionRequestSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return {"error": "validation_error", "message": err.messages}, 400

    values = data["values"]
    timestamps = data["timestamps"]
    model = data["model"]
    degree = data["degree"]

    if len(values) < 4:
        return {"error": "validation_error", "message": "values must have at least 4 elements"}, 400

    if len(values) != len(timestamps):
        return {"error": "validation_error", "message": "timestamps and values must have the same length"}, 400

    try:
        pd.to_datetime(timestamps, utc=True)
    except Exception:
        return {"error": "validation_error", "message": "timestamps contains invalid ISO-8601 dates"}, 400

    if model == "polynomial" and (degree < 1 or degree >= len(values)):
        return {
            "error": "validation_error",
            "message": f"degree must be >= 1 and < len(values) ({len(values)}), got {degree}",
        }, 400

    body = request.get_json(silent=True) or {}
    cache_key = f"regression:{hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}"

    try:
        cached = cache.get_cached(cache_key)
        if cached:
            return json.loads(cached), 200, {"X-Cache": "HIT"}
    except Exception:
        current_app.logger.warning("Redis unavailable, skipping cache lookup")

    try:
        if model == "polynomial":
            result = regression_service.polynomial_regression(values, timestamps, degree)
        else:
            result = regression_service.bayesian_regression(values, timestamps)
    except ValueError as err:
        return {"error": "validation_error", "message": str(err)}, 400
    except Exception:
        current_app.logger.exception("Unexpected error in regression endpoint")
        return {"error": "internal_error", "message": "An unexpected error occurred"}, 500

    try:
        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
    except Exception:
        current_app.logger.warning("Redis unavailable, skipping cache write")

    return result, 200, {"X-Cache": "MISS"}
