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
from services import regression_service

blp = Blueprint("regression", __name__, url_prefix="/analysis")


_ALLOWED_MODELS = {"polynomial", "bayesian"}

if _HAS_OPENAPI:
    class RegressionRequestSchema(Schema):
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
            metadata={"example": "polynomial"},
        )
        degree = fields.Integer(load_default=3, metadata={"example": 3})


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


def _handle_regression(data):
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


if _HAS_OPENAPI:
    @blp.route("/regression", methods=["POST"])
    @blp.arguments(RegressionRequestSchema, location="json")
    def post_regression(data):
        return _handle_regression(data)
else:
    @blp.route("/regression", methods=["POST"])
    def post_regression():
        data, errors = _load_request()
        if errors:
            return {"error": "validation_error", "message": errors}, 400
        return _handle_regression(data)
