from flask import request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError
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

    try:
        regression_service.fit_regression(
            data["values"],
            data["timestamps"],
            data["model"],
            data.get("degree", 3),
        )
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Regression not yet implemented (Card 4B1)",
        }, 501
