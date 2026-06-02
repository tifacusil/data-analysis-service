try:
    from flask_smorest import Blueprint  # type: ignore
except ModuleNotFoundError:
    from flask import Blueprint
from app import cache, consul
from app.config import Config

blp = Blueprint("health", __name__, url_prefix="/analysis")


def _import_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


@blp.route("/health", methods=["GET"])
def health():
    redis_status = "connected" if cache.ping() else "unavailable"
    consul_status = "registered" if consul.is_registered() else "unregistered"

    libs = {
        "pywt": _import_available("pywt"),
        "PyEMD": _import_available("PyEMD"),
        "statsmodels": _import_available("statsmodels"),
    }
    libs_status = {k: ("available" if v else "unavailable") for k, v in libs.items()}
    overall_status = "ok" if all(libs.values()) else "degraded"

    return {
        "status": overall_status,
        "redis": redis_status,
        "consul": consul_status,
        "version": Config.VERSION,
        "libs": libs_status,
    }, 200
