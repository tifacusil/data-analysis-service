import atexit
from flask import Flask
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

    public_prefix = (Config.PUBLIC_URL_PREFIX or "").strip()
    if public_prefix and not public_prefix.startswith("/"):
        public_prefix = f"/{public_prefix}"
    public_prefix = public_prefix.rstrip("/")
    url_prefix = public_prefix or None
    if url_prefix:
        app.config["OPENAPI_URL_PREFIX"] = url_prefix

    try:
        from flask_smorest import Api  # type: ignore
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

    from app import consul
    consul.register()
    atexit.register(consul.deregister)

    return app
