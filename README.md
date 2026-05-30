# data-analysis-service

Time-series analysis microservice for landslide monitoring (Bai et al., 2020).
Provides outlier detection, denoising, regression, and prediction over displacement
sensor data via a REST API.

> **Status:** skeleton (Card 4X0). All analysis endpoints return `501 Not Implemented`
> until cards 4A1–4B2 are completed. The `/health` endpoint is fully operational.

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [Configuration](#configuration)
- [Endpoints](#endpoints)
- [Running tests](#running-tests)
- [Adding a new algorithm (cards 4A1–4B2)](#adding-a-new-algorithm)
- [Deploy](#deploy)
- [Cards](#cards)

---

## Architecture overview

```
HTTP client
    │
    ▼
app/routes/          ← Flask blueprints: validate request, call service, shape response
    │
    ▼
services/            ← Business logic (NotImplementedError stubs until cards land)
    │
    ├── app/cache.py ← Redis wrapper (prefix analysis_cache:)
    └── app/consul.py← Consul registration (HTTP API via requests)
```

- **Framework:** Flask 3 + flask-smorest (OpenAPI/Swagger auto-generation)
- **Validation:** marshmallow schemas — invalid requests return `400` before the service is called
- **Cache:** Redis with configurable TTL (default 1 h)
- **Service registry:** Consul — `register()` on startup, `deregister()` on exit via `atexit`
- **Deploy:** systemd + Gunicorn on Ubuntu 24.04

---

## Getting started

### Prerequisites

- Python 3.11+ (tested with 3.12)
- Redis and Consul are **not required** to run locally — the service starts and `/health`
  responds even when they are unreachable.

### Setup

```bash
git clone <repo-url>
cd data-analysis-service

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt -r requirements-dev.txt
```

### Configure

```bash
cp .env.example .env
# Fill in values — at minimum leave defaults for local dev
```

### Run

```bash
FLASK_APP=main.py flask run --port 8090
```

The Swagger UI is available at `http://localhost:8090/swagger-ui`.

---

## Project structure

```
data-analysis-service/
├── app/
│   ├── __init__.py          # create_app() factory
│   ├── config.py            # env-var config (ANALYSIS__ prefix)
│   ├── cache.py             # Redis wrapper
│   ├── consul.py            # Consul register/deregister
│   └── routes/
│       ├── health.py        # GET /health
│       ├── outliers.py      # POST /analysis/outliers
│       ├── denoise.py       # POST /analysis/denoise
│       ├── regression.py    # POST /analysis/regression
│       └── predict.py       # POST /analysis/predict
├── services/
│   ├── outliers_service.py  # detect_outliers() — raises NotImplementedError
│   ├── denoise_service.py   # denoise()
│   ├── regression_service.py# fit_regression()
│   └── predict_service.py   # predict()
├── tests/
│   ├── conftest.py          # app fixture (Redis + Consul mocked)
│   ├── test_health.py
│   ├── test_outliers.py
│   ├── test_denoise.py
│   ├── test_regression.py
│   └── test_predict.py
├── deploy/
│   ├── data-analysis.service# systemd unit
│   └── .env.example
├── requirements.txt         # pinned production deps — do not edit
├── requirements-dev.txt     # pytest, flake8, flask-smorest, marshmallow, requests
└── .github/workflows/ci.yml # install + flake8 + pytest
```

---

## Configuration

All variables use the `ANALYSIS__` prefix. Section separators use double underscores
(`ANALYSIS__REDIS__HOST` → `config.REDIS_HOST`).

| Variable | Default | Description |
|---|---|---|
| `ANALYSIS__PORT` | `8090` | Server port |
| `ANALYSIS__HOST` | `0.0.0.0` | Bind address |
| `ANALYSIS__ENV` | `dev` | Environment (`dev` / `staging` / `prod`) |
| `ANALYSIS__VERSION` | `1.0.0` | Reported in `/health` |
| `ANALYSIS__INSTANCE_ID` | `data-analysis-01` | Consul service ID (must be unique per instance) |
| `ANALYSIS__REDIS__HOST` | `localhost` | Redis host |
| `ANALYSIS__REDIS__PORT` | `6379` | Redis port |
| `ANALYSIS__REDIS__PASSWORD` | _(empty)_ | Redis password |
| `ANALYSIS__REDIS__CACHE_TTL_SECONDS` | `3600` | Default cache TTL (1 h) |
| `ANALYSIS__CONSUL__HOST` | `localhost` | Consul host |
| `ANALYSIS__CONSUL__PORT` | `8500` | Consul HTTP port |
| `ANALYSIS__CONSUL__TOKEN` | _(empty)_ | Consul ACL token |
| `ANALYSIS__CONSUL__HEALTH_PORT` | `9090` | Port Consul uses for its health check |

---

## Endpoints

| Method | Path | Status | Card |
|---|---|---|---|
| `GET` | `/health` | Implemented | — |
| `POST` | `/analysis/outliers` | Stub (501) | 4A1 |
| `POST` | `/analysis/denoise` | Stub (501) | 4A2 |
| `POST` | `/analysis/regression` | Stub (501) | 4B1 |
| `POST` | `/analysis/predict` | Stub (501) | 4B2 |

### GET /health

Always returns `200`. Redis and Consul failures are reported in the body, not as HTTP errors.

```json
{
  "status": "ok",
  "redis": "connected",
  "consul": "registered",
  "version": "1.0.0"
}
```

### POST /analysis/outliers

```json
// Request
{
  "values":     [1.2, 3.4, 100.0, 2.1],
  "timestamps": ["2019-06-01T00:00:00Z", "2019-06-02T00:00:00Z", "..."],
  "method":     "3sigma"   // enum: "3sigma" | "chauvenet" | "iqr"
}

// 501 stub response
{ "error": "not_implemented", "message": "Outlier detection not yet implemented (Card 4A1)" }
```

### POST /analysis/denoise

```json
{
  "values":     [1.2, 3.4, 2.8, 2.1],
  "timestamps": ["2019-06-01T00:00:00Z", "..."],
  "method":     "wavelet"  // enum: "wavelet" | "emd" | "svm"
}
```

### POST /analysis/regression

```json
{
  "values":     [1.2, 3.4, 2.8, 2.1],
  "timestamps": ["2019-06-01T00:00:00Z", "..."],
  "model":      "polynomial",  // enum: "polynomial" | "bayesian"
  "degree":     3              // optional, default 3, only used for polynomial
}
```

### POST /analysis/predict

```json
{
  "values":      [1.2, 3.4, 2.8, 2.1],
  "timestamps":  ["2019-06-01T00:00:00Z", "..."],
  "model":       "arima",      // enum: "arima" | "gm11"
  "horizon":     30,
  "arima_order": [1, 1, 1]    // optional, only for arima
}
```

All endpoints return `400` with a descriptive `message` if the request body fails schema
validation (missing required field, wrong type, value outside enum).

---

## Running tests

```bash
pytest --tb=short -q
```

Tests run fully offline — Redis and Consul are mocked in `tests/conftest.py`. There are
18 tests covering:

- `200` from `/health` under connected and disconnected infra
- `501` from each analysis endpoint with a valid payload
- `400` from each endpoint with missing fields, wrong types, and invalid enum values

To run linting:

```bash
flake8 app/ services/ tests/
```

---

## Adding a new algorithm

Each card follows the same three-step pattern. Example for Card 4A1 (outlier detection):

**1. Implement the service** (`services/outliers_service.py`):

```python
import numpy as np  # now you can add imports

def detect_outliers(values, timestamps, method):
    if method == "3sigma":
        # ... real implementation
        return {"outliers": [...]}
    raise ValueError(f"Unknown method: {method}")
```

**2. Update the route** (`app/routes/outliers.py`) — remove the `try/except NotImplementedError`
block and return the service result with `200`.

**3. Update the test** (`tests/test_outliers.py`) — change the expected status from `501` to
`200` and assert the response body structure.

The cache helpers are ready to use:

```python
from app import cache
from app.config import Config

cached = cache.get_cached(key)
if cached is None:
    result = compute_something()
    cache.set_cached(key, result, Config.REDIS_CACHE_TTL_SECONDS)
```

---

## Deploy

The service runs as a dedicated `data-analysis` system user under systemd on Ubuntu 24.04.
Two workers run in a single Gunicorn process (not two separate systemd units).

### First-time setup on the server

```bash
# Create user and directories
sudo useradd --system --no-create-home --shell /usr/sbin/nologin data-analysis
sudo mkdir -p /opt/data-analysis /etc/data-analysis

# Deploy application code
sudo rsync -a . /opt/data-analysis/
sudo python3 -m venv /opt/data-analysis/.venv
sudo /opt/data-analysis/.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Write secrets (never commit this file)
sudo cp deploy/.env.example /etc/data-analysis/secrets
sudo nano /etc/data-analysis/secrets          # fill in real values
sudo chmod 600 /etc/data-analysis/secrets
sudo chown data-analysis: /etc/data-analysis/secrets

# Install and start the systemd unit
sudo cp deploy/data-analysis.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now data-analysis
```

### Routine commands

```bash
sudo systemctl status data-analysis
sudo journalctl -u data-analysis -f       # follow logs
sudo systemctl restart data-analysis
```

### Updating code

```bash
sudo rsync -a . /opt/data-analysis/
sudo systemctl restart data-analysis
```

---

## Cards

| Card | Description | Status |
|---|---|---|
| **4X0** | Service skeleton — structure, contracts, stubs, CI | Done |
| **4A1** | Outlier detection (3-sigma, Chauvenet, IQR) | Pending |
| **4A2** | Denoising (Wavelet, EMD, SVM) | Pending |
| **4B1** | Regression (Polynomial, Bayesian) | Pending |
| **4B2** | Prediction (ARIMA, GM(1,1)) | Pending |
