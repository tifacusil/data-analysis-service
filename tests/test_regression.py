VALID_PAYLOAD = {
    "values": [1.2, 3.4, 2.8, 2.1],
    "timestamps": [
        "2019-06-01T00:00:00Z",
        "2019-06-02T00:00:00Z",
        "2019-06-03T00:00:00Z",
        "2019-06-04T00:00:00Z",
    ],
    "model": "polynomial",
    "degree": 3,
}


def test_regression_returns_501(client):
    response = client.post("/analysis/regression", json=VALID_PAYLOAD)
    assert response.status_code == 501
    data = response.get_json()
    assert data["error"] == "not_implemented"


def test_regression_degree_defaults(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "degree"}
    response = client.post("/analysis/regression", json=payload)
    assert response.status_code == 501


def test_regression_missing_field_returns_400(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "model"}
    response = client.post("/analysis/regression", json=payload)
    assert response.status_code == 400


def test_regression_invalid_model_returns_400(client):
    payload = {**VALID_PAYLOAD, "model": "linear"}
    response = client.post("/analysis/regression", json=payload)
    assert response.status_code == 400
