from flask_smorest import Blueprint
from app import cache, consul
from app.config import Config

blp = Blueprint("health", __name__)


@blp.route("/health", methods=["GET"])
def health():
    redis_status = "connected" if cache.ping() else "unavailable"
    consul_status = "registered" if consul.is_registered() else "unregistered"
    return {
        "status": "ok",
        "redis": redis_status,
        "consul": consul_status,
        "version": Config.VERSION,
    }, 200
