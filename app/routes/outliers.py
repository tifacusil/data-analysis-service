from flask import request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError
from services import outliers_service

blp = Blueprint("outliers", __name__, url_prefix="/analysis")


class OutliersRequestSchema(Schema):
    values = fields.List(fields.Float(), required=True)
    timestamps = fields.List(fields.String(), required=True)
    method = fields.String(
        required=True,
        validate=validate.OneOf(["3sigma", "chauvenet", "iqr"]),
    )


@blp.route("/outliers", methods=["POST"])
def post_outliers():
    schema = OutliersRequestSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return {"error": "validation_error", "message": err.messages}, 400

    try:
        outliers_service.detect_outliers(
            data["values"], data["timestamps"], data["method"]
        )
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Outlier detection not yet implemented (Card 4A1)",
        }, 501
