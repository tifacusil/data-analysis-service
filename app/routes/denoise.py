from flask import request
try:
    from flask_smorest import Blueprint  # type: ignore
    from marshmallow import Schema, fields, validate
    _HAS_OPENAPI = True
except ModuleNotFoundError:
    from flask import Blueprint
    _HAS_OPENAPI = False
from app import cache
from app.config import Config
from services import denoise_service

blp = Blueprint("denoise", __name__, url_prefix="/analysis")


_ALLOWED_METHODS = {"wavelet", "emd", "svm"}

if _HAS_OPENAPI:
    class DenoiseRequestSchema(Schema):
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
        method = fields.String(
            required=True,
            validate=validate.OneOf(sorted(_ALLOWED_METHODS)),
            metadata={"example": "wavelet"},
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


if _HAS_OPENAPI:
    @blp.route("/denoise", methods=["POST"])
    @blp.arguments(DenoiseRequestSchema, location="json")
    def post_denoise(data):
        if len(data["values"]) != len(data["timestamps"]):
            return {
                "error": "validation_error",
                "message": {"timestamps": ["Length must match values."]},
            }, 400

        cache_key = cache.make_analysis_cache_key(data)
        cached = cache.get_cached_json(cache_key)
        if cached is not None:
            return cached, 200

        try:
            result = denoise_service.denoise(
                data["values"], data["timestamps"], data["method"]
            )
        except ValueError as err:
            return {"error": "validation_error", "message": str(err)}, 400

        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
        return result, 200
else:
    @blp.route("/denoise", methods=["POST"])
    def post_denoise():
        data, errors = _load_request()
        if errors:
            return {"error": "validation_error", "message": errors}, 400

        if len(data["values"]) != len(data["timestamps"]):
            return {
                "error": "validation_error",
                "message": {"timestamps": ["Length must match values."]},
            }, 400

        cache_key = cache.make_analysis_cache_key(data)
        cached = cache.get_cached_json(cache_key)
        if cached is not None:
            return cached, 200

        try:
            result = denoise_service.denoise(
                data["values"], data["timestamps"], data["method"]
            )
        except ValueError as err:
            return {"error": "validation_error", "message": str(err)}, 400

        cache.set_cached(cache_key, result, Config.REDIS_CACHE_TTL_SECONDS)
        return result, 200
