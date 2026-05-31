import json
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest


def _make_timestamps(n, start="2019-06-01"):
    base = datetime.fromisoformat(start)
    return [(base + timedelta(days=i)).isoformat() + "Z" for i in range(n)]


def _parabola_payload(n=10, degree=2, noise=0.5, seed=42):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 10, n)
    values = (2 * x**2 - 3 * x + 1 + rng.normal(0, noise, n)).tolist()
    return {
        "values": values,
        "timestamps": _make_timestamps(n),
        "model": "polynomial",
        "degree": degree,
    }


def _line_payload(n=10, noise=0.5, seed=42):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 10, n)
    values = (1.5 * x + 2 + rng.normal(0, noise, n)).tolist()
    return {
        "values": values,
        "timestamps": _make_timestamps(n),
        "model": "bayesian",
    }


def _no_cache():
    return (
        patch("app.cache.get_cached", return_value=None),
        patch("app.cache.set_cached"),
    )


def test_polynomial_basic(client):
    payload = _parabola_payload(n=10, degree=2)
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "polynomial"
    assert data["degree"] == 2
    assert len(data["fitted_values"]) == 10
    assert len(data["coefficients"]) == 3
    assert 0.0 <= data["r2_score"] <= 1.0


def test_bayesian_basic(client):
    payload = _line_payload(n=10)
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "bayesian"
    assert data["degree"] is None
    assert len(data["fitted_values"]) == 10
    assert len(data["coefficients"]) == 2
    assert 0.0 <= data["r2_score"] <= 1.0


def test_invalid_model(client):
    payload = {**_parabola_payload(), "model": "linear"}
    r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 400


def test_too_few_values(client):
    payload = {
        "values": [1.0, 2.0, 3.0],
        "timestamps": _make_timestamps(3),
        "model": "polynomial",
        "degree": 2,
    }
    r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 400


def test_mismatched_lengths(client):
    payload = {
        "values": [1.0, 2.0, 3.0, 4.0, 5.0],
        "timestamps": _make_timestamps(4),
        "model": "polynomial",
        "degree": 2,
    }
    r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 400


def test_degree_too_high(client):
    payload = {
        "values": [1.0, 2.0, 3.0, 4.0, 5.0],
        "timestamps": _make_timestamps(5),
        "model": "polynomial",
        "degree": 10,
    }
    r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 400


def test_invalid_timestamp(client):
    payload = {
        "values": [1.0, 2.0, 3.0, 4.0],
        "timestamps": ["2019-06-01T00:00:00Z", "not-a-date", "2019-06-03T00:00:00Z", "2019-06-04T00:00:00Z"],
        "model": "polynomial",
        "degree": 2,
    }
    r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 400


def test_cache_hit(client):
    payload = _parabola_payload(n=10, degree=2)

    with patch("app.cache.get_cached", return_value=None), \
         patch("app.cache.set_cached"):
        r1 = client.post("/analysis/regression", json=payload)

    assert r1.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS"
    result_json = json.dumps(r1.get_json())

    with patch("app.cache.get_cached", return_value=result_json), \
         patch("app.cache.set_cached"):
        r2 = client.post("/analysis/regression", json=payload)

    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT"


def test_cache_unavailable(client):
    payload = _parabola_payload(n=10, degree=2)
    with patch("app.cache.get_cached", side_effect=Exception("Redis down")), \
         patch("app.cache.set_cached", side_effect=Exception("Redis down")):
        r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 200


def test_r2_score_reasonable(client):
    n = 20
    x = np.linspace(0, 10, n)
    values = (2 * x**2 - 3 * x + 1).tolist()
    timestamps = _make_timestamps(n)
    payload = {
        "values": values,
        "timestamps": timestamps,
        "model": "polynomial",
        "degree": 2,
    }
    with patch("app.cache.get_cached", return_value=None), patch("app.cache.set_cached"):
        r = client.post("/analysis/regression", json=payload)
    assert r.status_code == 200
    assert r.get_json()["r2_score"] > 0.99
