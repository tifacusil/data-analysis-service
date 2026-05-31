VALID_PAYLOAD = {
    "values": [1.2, 3.4, 2.8, 2.1],
    "timestamps": [
        "2019-06-01T00:00:00Z",
        "2019-06-02T00:00:00Z",
        "2019-06-03T00:00:00Z",
        "2019-06-04T00:00:00Z",
    ],
    "method": "wavelet",
}


def test_denoise_wavelet_returns_200(client):
    response = client.post("/analysis/denoise", json=VALID_PAYLOAD)
    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "wavelet"
    assert isinstance(data["denoised_values"], list)
    assert len(data["denoised_values"]) == len(VALID_PAYLOAD["values"])
    assert "params" in data


def test_denoise_emd_returns_200(client):
    payload = {**VALID_PAYLOAD, "method": "emd"}
    response = client.post("/analysis/denoise", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "emd"
    assert isinstance(data["denoised_values"], list)
    assert len(data["denoised_values"]) == len(VALID_PAYLOAD["values"])
    assert "params" in data


def test_denoise_svm_returns_200(client):
    payload = {**VALID_PAYLOAD, "method": "svm"}
    response = client.post("/analysis/denoise", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "svm"
    assert isinstance(data["denoised_values"], list)
    assert len(data["denoised_values"]) == len(VALID_PAYLOAD["values"])
    assert "params" in data


def test_denoise_missing_field_returns_400(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "method"}
    response = client.post("/analysis/denoise", json=payload)
    assert response.status_code == 400


def test_denoise_invalid_method_returns_400(client):
    payload = {**VALID_PAYLOAD, "method": "fft"}
    response = client.post("/analysis/denoise", json=payload)
    assert response.status_code == 400
