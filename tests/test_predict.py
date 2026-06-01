import json
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd


def test_predict_returns_200(client):
    response = client.post("/analysis/predict", json=VALID_PAYLOAD)
    assert response.status_code == 200
    data = response.get_json()
    assert "predicted_values" in data
    assert "predicted_timestamps" in data
    assert len(data["predicted_values"]) == VALID_PAYLOAD["horizon"]
    assert len(data["predicted_timestamps"]) == VALID_PAYLOAD["horizon"]
    assert data["model"] in {"arima", "gm11"}


def test_predict_without_arima_order(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "arima_order"}
    response = client.post("/analysis/predict", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert "predicted_values" in data
    assert len(data["predicted_values"]) == VALID_PAYLOAD["horizon"]
def _make_timestamps(n, start="2019-06-01"):
    base = datetime.fromisoformat(start)
    return [(base + timedelta(days=i)).isoformat() + "Z" for i in range(n)]


def _arima_payload(n=10, horizon=5, order=None):
    rng = np.random.default_rng(42)
    x = np.arange(n)
    values = (2.0 * x + 5.0 + rng.normal(0, 0.3, n)).tolist()
    payload = {
        "values": values,
        "timestamps": _make_timestamps(n),
        "model": "arima",
        "horizon": horizon,
    }
    if order is not None:
        payload["arima_order"] = list(order)
    return payload


def _gm11_payload(n=8, horizon=3):
    values = [float(np.exp(0.1 * k)) for k in range(n)]
    return {
        "values": values,
        "timestamps": _make_timestamps(n),
        "model": "gm11",
        "horizon": horizon,
    }


VALID_PAYLOAD = {
    "values": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "timestamps": _make_timestamps(10),
    "model": "arima",
    "horizon": 5,
    "arima_order": [1, 1, 1],
}


def test_arima_basic(client):
    payload = _arima_payload(n=10, horizon=5)
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "arima"
    assert data["order"] == [1, 1, 1]
    assert data["horizon"] == 5
    assert len(data["predicted_values"]) == 5
    assert len(data["predicted_timestamps"]) == 5
    assert data["confidence_lower"] is not None and len(data["confidence_lower"]) == 5
    assert data["confidence_upper"] is not None and len(data["confidence_upper"]) == 5


def test_gm11_basic(client):
    payload = _gm11_payload(n=8, horizon=3)
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "gm11"
    assert data["order"] is None
    assert data["horizon"] == 3
    assert len(data["predicted_values"]) == 3
    assert len(data["predicted_timestamps"]) == 3
    assert data["confidence_lower"] is None
    assert data["confidence_upper"] is None


def test_gm11_accuracy(client):
    values_exact = [float(np.exp(0.1 * k)) for k in range(8)]
    expected_next = [float(np.exp(0.1 * k)) for k in range(8, 11)]
    payload = {
        "values": values_exact,
        "timestamps": _make_timestamps(8),
        "model": "gm11",
        "horizon": 3,
    }
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200
    predicted = r.get_json()["predicted_values"]
    for pred, expected in zip(predicted, expected_next):
        assert abs(pred - expected) / expected < 0.05, (
            f"GM(1,1) prediction {pred:.4f} deviates >5% from expected {expected:.4f}"
        )


def test_invalid_model(client):
    payload = {**_arima_payload(), "model": "lstm"}
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_too_few_values(client):
    payload = {
        "values": [1.0, 2.0, 3.0],
        "timestamps": _make_timestamps(3),
        "model": "arima",
        "horizon": 2,
    }
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_horizon_zero(client):
    payload = {**_arima_payload(), "horizon": 0}
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_horizon_too_large(client):
    payload = {**_arima_payload(), "horizon": 366}
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_mismatched_lengths(client):
    payload = {
        "values": [1.0, 2.0, 3.0, 4.0, 5.0],
        "timestamps": _make_timestamps(4),
        "model": "arima",
        "horizon": 2,
    }
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_invalid_timestamp(client):
    payload = {
        "values": [1.0, 2.0, 3.0, 4.0],
        "timestamps": ["2019-06-01T00:00:00Z", "not-a-date", "2019-06-03T00:00:00Z", "2019-06-04T00:00:00Z"],
        "model": "arima",
        "horizon": 2,
    }
    r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 400


def test_arima_custom_order(client):
    payload = _arima_payload(n=10, horizon=3, order=[2, 1, 0])
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200
    assert r.get_json()["order"] == [2, 1, 0]


def test_cache_hit(client):
    payload = _arima_payload(n=10, horizon=5)

    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r1 = client.post("/analysis/predict", json=payload)
    assert r1.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS"
    result_json = json.dumps(r1.get_json())

    with patch("app.cache.get_cached", return_value=result_json), patch("app.cache.set_cached"):
        r2 = client.post("/analysis/predict", json=payload)
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT"


def test_cache_unavailable(client):
    payload = _gm11_payload(n=8, horizon=3)
    with patch("app.cache.get_cached", side_effect=Exception("Redis down")), \
         patch("app.cache.set_cached", side_effect=Exception("Redis down")):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200


def test_predicted_timestamps_are_future(client):
    payload = _arima_payload(n=10, horizon=5)
    last_input = pd.Timestamp("2019-06-10T00:00:00Z")

    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/predict", json=payload)
    assert r.status_code == 200
    for ts_str in r.get_json()["predicted_timestamps"]:
        ts = pd.Timestamp(ts_str)
        assert ts > last_input, f"Predicted timestamp {ts_str} is not after last input"
