VALID_PAYLOAD = {
    "values": [1.2, 3.4, 2.8, 2.1],
    "timestamps": [
        "2019-06-01T00:00:00Z",
        "2019-06-02T00:00:00Z",
        "2019-06-03T00:00:00Z",
        "2019-06-04T00:00:00Z",
    ],
    "model": "arima",
    "horizon": 30,
    "arima_order": [1, 1, 1],
}


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


def test_predict_missing_field_returns_400(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "horizon"}
    response = client.post("/analysis/predict", json=payload)
    assert response.status_code == 400


def test_predict_invalid_model_returns_400(client):
    payload = {**VALID_PAYLOAD, "model": "lstm"}
    response = client.post("/analysis/predict", json=payload)
    assert response.status_code == 400
