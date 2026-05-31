from unittest.mock import patch


def test_health_returns_200(client):
    with patch("app.cache.ping", return_value=True), \
         patch("app.consul.is_registered", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200


def test_health_body(client):
    with patch("app.cache.ping", return_value=True), \
         patch("app.consul.is_registered", return_value=True):
        response = client.get("/health")
    data = response.get_json()
    assert data["status"] in {"ok", "degraded"}
    assert data["redis"] == "connected"
    assert data["consul"] == "registered"
    assert "version" in data
    assert "libs" in data


def test_health_redis_unavailable(client):
    with patch("app.cache.ping", return_value=False), \
         patch("app.consul.is_registered", return_value=False):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["redis"] == "unavailable"
    assert data["consul"] == "unregistered"
