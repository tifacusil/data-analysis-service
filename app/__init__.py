import atexit
from flask import Flask
from werkzeug.exceptions import UnprocessableEntity
from app.config import Config

_ALLOWED_ORIGINS = [
    "https://vite-ews-frontend.vercel.app",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    @app.errorhandler(UnprocessableEntity)
    def _handle_unprocessable_entity(err: UnprocessableEntity):
        data = getattr(err, "data", None) or {}
        messages = data.get("messages")
        if messages is None:
            return {"error": "validation_error", "message": "Invalid request body."}, 400
        return {"error": "validation_error", "message": messages}, 400

    route_prefix = (Config.ROUTE_PREFIX or "").strip()
    if route_prefix and not route_prefix.startswith("/"):
        route_prefix = f"/{route_prefix}"
    route_prefix = route_prefix.rstrip("/")
    url_prefix = route_prefix or None
    if url_prefix:
        app.config["OPENAPI_URL_PREFIX"] = url_prefix

    try:
        from flask_smorest import Api  # type: ignore
        import marshmallow
    except ModuleNotFoundError:
        Api = None  # type: ignore[assignment]

    api = Api(app) if Api is not None else None
    try:
        from flask_cors import CORS  # type: ignore
        CORS(app, origins=_ALLOWED_ORIGINS)
    except ModuleNotFoundError:
        pass

    from app.routes.health import blp as health_blp
    from app.routes.outliers import blp as outliers_blp
    from app.routes.denoise import blp as denoise_blp
    from app.routes.regression import blp as regression_blp
    from app.routes.predict import blp as predict_blp

    if api is not None:
        api.register_blueprint(health_blp, url_prefix=url_prefix)
        api.register_blueprint(outliers_blp, url_prefix=url_prefix)
        api.register_blueprint(denoise_blp, url_prefix=url_prefix)
        api.register_blueprint(regression_blp, url_prefix=url_prefix)
        api.register_blueprint(predict_blp, url_prefix=url_prefix)
    else:
        app.register_blueprint(health_blp, url_prefix=url_prefix)
        app.register_blueprint(outliers_blp, url_prefix=url_prefix)
        app.register_blueprint(denoise_blp, url_prefix=url_prefix)
        app.register_blueprint(regression_blp, url_prefix=url_prefix)
        app.register_blueprint(predict_blp, url_prefix=url_prefix)

    from app.metrics import init_metrics
    init_metrics(app)

    from app import consul
    consul.register()
    atexit.register(consul.deregister)

    return app
