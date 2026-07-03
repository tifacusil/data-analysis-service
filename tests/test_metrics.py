from unittest.mock import patch

from prometheus_client import CONTENT_TYPE_LATEST


def test_metrics_endpoint_exposition(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == CONTENT_TYPE_LATEST


def test_metrics_counts_http_requests(client):
    with patch("app.cache.ping", return_value=True), \
         patch("app.consul.is_registered", return_value=True):
        client.get("/analysis/health")

    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    assert 'path="/analysis/health"' in body
    assert "http_request_duration_seconds_bucket" in body


def test_metrics_self_excluded(client):
    # Scraping /metrics must not appear in http_requests_total.
    client.get("/metrics")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'path="/metrics"' not in body


def test_metrics_unmatched_path_bounded(client):
    client.get("/no/such/route/xyz")
    body = client.get("/metrics").get_data(as_text=True)
    assert "/no/such/route/xyz" not in body
    assert "__unmatched__" in body
