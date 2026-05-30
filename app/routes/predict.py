from flask import request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate, ValidationError
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

    try:
        predict_service.predict(
            data["values"],
            data["timestamps"],
            data["model"],
            data["horizon"],
            data.get("arima_order"),
        )
    except NotImplementedError:
        return {
            "error": "not_implemented",
            "message": "Prediction not yet implemented (Card 4B2)",
        }, 501
