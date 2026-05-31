from flask import request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError
from services import denoise_service

blp = Blueprint("denoise", __name__, url_prefix="/analysis")


class DenoiseRequestSchema(Schema):
    values = fields.List(fields.Float(), required=True)
    timestamps = fields.List(fields.String(), required=True)
    method = fields.String(
        required=True,
        validate=validate.OneOf(["wavelet", "emd", "svm"]),
    )


@blp.route("/denoise", methods=["POST"])
def post_denoise():
    schema = DenoiseRequestSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return {"error": "validation_error", "message": err.messages}, 400

    try:
        if len(data["values"]) != len(data["timestamps"]):
            return {
                "error": "validation_error",
                "message": {"timestamps": ["Length must match values."]},
            }, 400
        result = denoise_service.denoise(data["values"], data["timestamps"], data["method"])
        return result, 200
    except ValueError as err:
        return {"error": "validation_error", "message": str(err)}, 400
