# data-analysis-service

Time-series analysis microservice for landslide / displacement sensor monitoring.
Provides outlier detection, denoising, regression, and prediction over sensor data via a REST API.

- **Base URL (local):** `http://localhost:8090`
- **Base URL (production):** configure via `ANALYSIS__PUBLIC_URL_PREFIX`
- **Route prefix:** all paths below assume `ANALYSIS__ROUTE_PREFIX=/analysis` (the deployed default)
- **Swagger UI:** `{base}/swagger-ui`
- **Content-Type:** all requests and responses are `application/json`
- **Auth:** none (CORS restricted to allowed origins)

---

## Table of contents

- [Endpoints at a glance](#endpoints-at-a-glance)
- [Common request shape](#common-request-shape)
- [Common error shape](#common-error-shape)
- [GET /analysis/health](#get-analysishealth)
- [POST /analysis/outliers](#post-analysisoutliers)
- [POST /analysis/denoise](#post-analysisdenoise)
- [POST /analysis/regression](#post-analysisregression)
- [POST /analysis/predict](#post-analysispredict)
- [Caching](#caching)
- [Running locally](#running-locally)
- [Configuration](#configuration)
- [Running tests](#running-tests)
- [Deploy](#deploy)

---

## Endpoints at a glance

| Method | Path | Description |
|---|---|---|
| `GET` | `/analysis/health` | Service liveness + dependency status |
| `POST` | `/analysis/outliers` | Detect outliers in a time series |
| `POST` | `/analysis/denoise` | Remove noise from a time series |
| `POST` | `/analysis/regression` | Fit a regression curve to a time series |
| `POST` | `/analysis/predict` | Forecast future values from a time series |

---

## Common request shape

Every analysis endpoint accepts a JSON body with at least:

| Field | Type | Required | Description |
|---|---|---|---|
| `values` | `float[]` | Yes | Sensor readings (non-empty, no NaN/Inf) |
| `timestamps` | `string[]` | Yes | ISO-8601 timestamps, same length as `values` |
| `method` / `model` | `string` | Yes | Algorithm selector (see each endpoint) |

**Minimum data points:** 4 for `/predict` and `/regression`. The `values` and `timestamps` arrays must always have equal length.

**Timestamp format:** ISO-8601, e.g. `"2024-01-15T08:00:00Z"` or `"2024-01-15T08:00:00+00:00"`.

---

## Common error shape

All `400` responses follow:

```json
{
  "error": "validation_error",
  "message": "human-readable description or field-level object"
}
```

Field-level errors (when multiple fields are invalid):

```json
{
  "error": "validation_error",
  "message": {
    "values": ["Must be a non-empty list."],
    "method": ["Must be one of: 3sigma, chauvenet, iqr."]
  }
}
```

Unexpected server errors return `500`:

```json
{ "error": "internal_error", "message": "An unexpected error occurred" }
```

---

## GET /analysis/health

Returns service liveness and the status of dependencies. Always `200` — Redis/Consul failures appear in the body, not as HTTP errors.

### Response `200`

```json
{
  "status": "ok",
  "redis": "connected",
  "consul": "registered",
  "version": "1.0.0",
  "libs": {
    "pywt": "available",
    "PyEMD": "available",
    "statsmodels": "available"
  }
}
```

| Field | Values | Description |
|---|---|---|
| `status` | `"ok"` \| `"degraded"` | `"degraded"` if any required lib is missing |
| `redis` | `"connected"` \| `"unavailable"` | |
| `consul` | `"registered"` \| `"unregistered"` | |
| `libs` | object | Each lib is `"available"` or `"unavailable"` |

---

## POST /analysis/outliers

Detects data points that deviate significantly from the rest of the series.

### Request

```json
{
  "values":     [1.2, 3.4, 100.0, 2.1, 2.5],
  "timestamps": [
    "2024-01-01T00:00:00Z",
    "2024-01-02T00:00:00Z",
    "2024-01-03T00:00:00Z",
    "2024-01-04T00:00:00Z",
    "2024-01-05T00:00:00Z"
  ],
  "method": "3sigma"
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `method` | string | Yes | `"3sigma"` \| `"chauvenet"` \| `"iqr"` |

**Methods:**
- `3sigma` — flags values outside mean ± 3 standard deviations
- `iqr` — flags values outside Q1 − 1.5·IQR and Q3 + 1.5·IQR
- `chauvenet` — probabilistic criterion; flags values unlikely given the distribution

### Response `200`

```json
{
  "method": "3sigma",
  "outliers": [
    {
      "index": 2,
      "timestamp": "2024-01-03T00:00:00Z",
      "value": 100.0,
      "threshold_upper": 54.3,
      "threshold_lower": -47.8,
      "criterion": "exceeds_upper"
    }
  ],
  "statistics": {
    "mean": 21.84,
    "std": 38.22,
    "n": 5,
    "outlier_count": 1
  }
}
```

**`outliers` item fields:**

| Field | Present in | Description |
|---|---|---|
| `index` | all | Position in the original `values` array |
| `timestamp` | all | Corresponding timestamp |
| `value` | all | The outlier value |
| `threshold_upper` | `3sigma`, `iqr` | Upper bound used |
| `threshold_lower` | `3sigma`, `iqr` | Lower bound used |
| `criterion` | `3sigma`, `iqr` | `"exceeds_upper"` or `"exceeds_lower"` |
| `z_score` | `chauvenet` | Z-score of this value |
| `probability` | `chauvenet` | Tail probability |

---

## POST /analysis/denoise

Smooths a noisy time series using the selected algorithm.

### Request

```json
{
  "values":     [1.2, 3.4, 2.8, 2.1, 3.0, 2.5],
  "timestamps": [
    "2024-01-01T00:00:00Z",
    "2024-01-02T00:00:00Z",
    "2024-01-03T00:00:00Z",
    "2024-01-04T00:00:00Z",
    "2024-01-05T00:00:00Z",
    "2024-01-06T00:00:00Z"
  ],
  "method": "wavelet"
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `method` | string | Yes | `"wavelet"` \| `"emd"` \| `"svm"` |

**Methods:**
- `wavelet` — Discrete Wavelet Transform (db4) with soft thresholding (requires `pywt`)
- `emd` — Empirical Mode Decomposition; removes high-frequency IMFs (requires `PyEMD`)
- `svm` — SVR with RBF kernel fits a smooth curve through the time index (requires `scikit-learn`)

If an optional library is missing, the endpoint falls back to a moving-average smoother automatically.

### Response `200`

```json
{
  "denoised_values": [1.85, 2.60, 2.77, 2.53, 2.70, 2.62],
  "method": "wavelet",
  "params": {
    "wavelet": "db4",
    "level": 2,
    "threshold": 1.43,
    "mode": "soft",
    "sigma": 0.61
  }
}
```

**`params` fields vary by method:**

`wavelet`:

| Field | Description |
|---|---|
| `wavelet` | Wavelet family used (`"db4"`) |
| `level` | Decomposition level |
| `threshold` | Applied threshold value |
| `mode` | Thresholding mode (`"soft"`) |
| `sigma` | Estimated noise level |

`emd`:

| Field | Description |
|---|---|
| `imf_count` | Total number of IMFs decomposed |
| `removed_imfs` | Indices of removed high-frequency IMFs |
| `strategy` | Selection strategy (`"zcr_quantile"`) |
| `quantile` | Quantile threshold used |
| `zcrs` | Zero-crossing rate per IMF |

`svm`:

| Field | Description |
|---|---|
| `kernel` | SVR kernel (`"rbf"`) |
| `C` | Regularisation parameter |
| `epsilon` | Epsilon in the loss function |
| `gamma` | Kernel coefficient |
| `feature` | Feature used (`"index"`) |

Fallback (library unavailable):

```json
{ "fallback": "moving_average", "window": 5 }
```

---

## POST /analysis/regression

Fits a curve to the time series and returns fitted values and goodness-of-fit metrics.

### Request

```json
{
  "values":     [1.2, 3.4, 2.8, 4.1, 5.0, 4.7],
  "timestamps": [
    "2024-01-01T00:00:00Z",
    "2024-01-02T00:00:00Z",
    "2024-01-03T00:00:00Z",
    "2024-01-04T00:00:00Z",
    "2024-01-05T00:00:00Z",
    "2024-01-06T00:00:00Z"
  ],
  "model":  "polynomial",
  "degree": 3
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `model` | string | Yes | — | `"polynomial"` \| `"bayesian"` |
| `degree` | integer | No | `3` | Polynomial degree; must satisfy `1 ≤ degree < len(values)`. Ignored for `bayesian`. |

**Models:**
- `polynomial` — least-squares polynomial fit of given degree
- `bayesian` — Bayesian Ridge linear regression (linear in time)

### Response `200`

```json
{
  "coefficients":  [0.0003, -0.002, 0.21, 1.1],
  "fitted_values": [1.31, 2.98, 3.05, 4.02, 4.89, 4.75],
  "r2_score":      0.982,
  "model":         "polynomial",
  "degree":        3
}
```

| Field | Description |
|---|---|
| `coefficients` | Polynomial coefficients highest-degree first; for `bayesian`: `[intercept, slope]` |
| `fitted_values` | Fitted value at each input timestamp (same length as `values`) |
| `r2_score` | Coefficient of determination (0–1; higher is better) |
| `degree` | Degree used (`null` for `bayesian`) |

---

## POST /analysis/predict

Forecasts future values beyond the last observed timestamp.

### Request

```json
{
  "values":      [1.2, 3.4, 2.8, 4.1, 5.0, 4.7],
  "timestamps":  [
    "2024-01-01T00:00:00Z",
    "2024-01-02T00:00:00Z",
    "2024-01-03T00:00:00Z",
    "2024-01-04T00:00:00Z",
    "2024-01-05T00:00:00Z",
    "2024-01-06T00:00:00Z"
  ],
  "model":       "arima",
  "horizon":     7,
  "arima_order": [1, 1, 1]
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `model` | string | Yes | — | `"arima"` \| `"gm11"` |
| `horizon` | integer | Yes | — | Steps to forecast (1–365) |
| `arima_order` | `[p, d, q]` | No | `[1, 1, 1]` | ARIMA order; 3 non-negative integers. Only used for `arima`. |

**Models:**
- `arima` — AutoRegressive Integrated Moving Average; best for longer series with trend/seasonality
- `gm11` — Grey Model GM(1,1); best for short series (4+ points); no confidence intervals

**Minimum data:** 4 values required by both models.

### Response `200`

Headers include `X-Cache: HIT | MISS`.

```json
{
  "predicted_values":     [5.1, 5.4, 5.6, 5.8, 5.9, 6.0, 6.1],
  "predicted_timestamps": [
    "2024-01-07T00:00:00Z",
    "2024-01-08T00:00:00Z",
    "2024-01-09T00:00:00Z",
    "2024-01-10T00:00:00Z",
    "2024-01-11T00:00:00Z",
    "2024-01-12T00:00:00Z",
    "2024-01-13T00:00:00Z"
  ],
  "confidence_lower": [4.7, 4.8, 4.9, 5.0, 5.0, 5.0, 5.0],
  "confidence_upper": [5.5, 6.0, 6.3, 6.6, 6.8, 7.0, 7.2],
  "model":   "arima",
  "horizon": 7,
  "order":   [1, 1, 1]
}
```

| Field | Description |
|---|---|
| `predicted_values` | Forecasted values; length = `horizon` |
| `predicted_timestamps` | Future timestamps inferred from the input frequency |
| `confidence_lower` | 95 % lower bound (`null` for `gm11`) |
| `confidence_upper` | 95 % upper bound (`null` for `gm11`) |
| `order` | ARIMA order used (`null` for `gm11`) |

---

## Caching

All analysis endpoints cache results in Redis (default TTL: 1 hour). The cache key is a SHA-256 hash of the exact request body. Identical requests return the cached result immediately — the `X-Cache` header (`HIT` / `MISS`) indicates cache status on `/predict` and `/regression`. Redis is optional; the service degrades gracefully when it is unreachable.

---

## Running locally

```bash
git clone <repo-url>
cd data-analysis-service

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

FLASK_APP=main.py flask run --port 8090
```

Swagger UI: `http://localhost:8090/swagger-ui`

Redis and Consul are optional — the service starts and all endpoints work without them.

---

## Configuration

All variables use the `ANALYSIS__` prefix.

| Variable | Default | Description |
|---|---|---|
| `ANALYSIS__PORT` | `8090` | Server port |
| `ANALYSIS__HOST` | `0.0.0.0` | Bind address |
| `ANALYSIS__ENV` | `dev` | Environment (`dev` / `staging` / `prod`) |
| `ANALYSIS__VERSION` | `1.0.0` | Reported in `/health` |
| `ANALYSIS__INSTANCE_ID` | `data-analysis-01` | Consul service ID (unique per instance) |
| `ANALYSIS__ROUTE_PREFIX` | _(empty)_ | Optional URL prefix for all routes |
| `ANALYSIS__PUBLIC_URL_PREFIX` | _(empty)_ | Base URL reported in OpenAPI spec |
| `ANALYSIS__REDIS__HOST` | `localhost` | Redis host |
| `ANALYSIS__REDIS__PORT` | `6379` | Redis port |
| `ANALYSIS__REDIS__PASSWORD` | _(empty)_ | Redis password |
| `ANALYSIS__REDIS__CACHE_TTL_SECONDS` | `3600` | Cache TTL in seconds |
| `ANALYSIS__CONSUL__HOST` | `localhost` | Consul host |
| `ANALYSIS__CONSUL__PORT` | `8500` | Consul HTTP port |
| `ANALYSIS__CONSUL__TOKEN` | _(empty)_ | Consul ACL token |
| `ANALYSIS__CONSUL__HEALTH_PORT` | `9090` | Port Consul uses for health checks |

---

## Running tests

```bash
pytest --tb=short -q
```

Tests run fully offline — Redis and Consul are mocked. Linting:

```bash
flake8 app/ services/ tests/
```

---

## Deploy

The service runs under systemd + Gunicorn on Ubuntu 24.04.

### First-time setup

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin data-analysis
sudo mkdir -p /opt/data-analysis /etc/data-analysis

sudo rsync -a . /opt/data-analysis/
sudo python3 -m venv /opt/data-analysis/.venv
sudo /opt/data-analysis/.venv/bin/pip install -r requirements.txt

sudo cp deploy/.env.example /etc/data-analysis/secrets
sudo nano /etc/data-analysis/secrets
sudo chmod 600 /etc/data-analysis/secrets
sudo chown data-analysis: /etc/data-analysis/secrets

sudo cp deploy/data-analysis.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now data-analysis
```

### Routine commands

```bash
sudo systemctl status data-analysis
sudo journalctl -u data-analysis -f
sudo systemctl restart data-analysis
```

### Updating code

```bash
sudo rsync -a . /opt/data-analysis/
sudo systemctl restart data-analysis
```
