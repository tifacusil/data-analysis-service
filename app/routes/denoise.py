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
        denoise_service.denoise(
            data["values"], data["timestamps"], data["method"]
        )
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Denoising not yet implemented (Card 4A2)",
        }, 501
