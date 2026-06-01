VALID_PAYLOAD = {
    "values": [1.2, 3.4, 100.0, 2.1],
    "timestamps": [
        "2019-06-01T00:00:00Z",
        "2019-06-02T00:00:00Z",
        "2019-06-03T00:00:00Z",
        "2019-06-04T00:00:00Z",
    ],
    "method": "3sigma",
}


def test_outliers_returns_200(client):
    response = client.post("/analysis/outliers", json=VALID_PAYLOAD)
    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "3sigma"
    assert "outliers" in data
    assert "statistics" in data
    assert data["statistics"]["n"] == 4


def test_outliers_missing_field_returns_400(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "values"}
    response = client.post("/analysis/outliers", json=payload)
    assert response.status_code == 400


def test_outliers_invalid_method_returns_400(client):
    payload = {**VALID_PAYLOAD, "method": "unknown"}
    response = client.post("/analysis/outliers", json=payload)
    assert response.status_code == 400


def test_outliers_wrong_type_returns_400(client):
    payload = {**VALID_PAYLOAD, "values": "not-a-list"}
    response = client.post("/analysis/outliers", json=payload)
    assert response.status_code == 400
