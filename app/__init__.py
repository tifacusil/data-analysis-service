import atexit
from flask import Flask
from app.config import Config


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    try:
        from flask_smorest import Api  # type: ignore
    except ModuleNotFoundError:
        Api = None  # type: ignore[assignment]

    api = Api(app) if Api is not None else None

    from app.routes.health import blp as health_blp
    from app.routes.outliers import blp as outliers_blp
    from app.routes.denoise import blp as denoise_blp
    from app.routes.regression import blp as regression_blp
    from app.routes.predict import blp as predict_blp

    if api is not None:
        api.register_blueprint(health_blp)
        api.register_blueprint(outliers_blp)
        api.register_blueprint(denoise_blp)
        api.register_blueprint(regression_blp)
        api.register_blueprint(predict_blp)
    else:
        app.register_blueprint(health_blp)
        app.register_blueprint(outliers_blp)
        app.register_blueprint(denoise_blp)
        app.register_blueprint(regression_blp)
        app.register_blueprint(predict_blp)

    from app import consul
    consul.register()
    atexit.register(consul.deregister)

    return app
