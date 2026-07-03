# `/metrics` endpoint

Single Prometheus scrape endpoint for the whole service. HTTP instrumentation
registers on the **default `prometheus_client` registry**, so one `/metrics`
exposes everything.

- **Served by:** Flask (`app/__init__.py::create_app`), instrumentation in
  `app/metrics.py`, route `GET /metrics`.
- **Path:** root, **no `ANALYSIS__ROUTE_PREFIX` and no `/analysis` blueprint
  prefix** — Prometheus scrapes the pod/host port directly, not through the
  gateway.
- **Content-Type:** `text/plain; version=0.0.4; charset=utf-8`
  (`prometheus_client.CONTENT_TYPE_LATEST`, set via `content_type`).
- **Body:** `prometheus_client.generate_latest()` — Prometheus text exposition
  format.
- **Self-exclusion:** requests to `/metrics` are skipped by the `after_request`
  hook, so scrapes don't inflate `http_requests_total`.

> This service is **Flask/WSGI, HTTP only**. There is no gRPC and no FastAPI —
> earlier drafts of this doc described a different stack.

---

## Multiprocess (gunicorn)

Runs under gunicorn with `--workers 2` (`deploy/data-analysis.service`). The
default `prometheus_client` registry is **per-process**, so without extra setup
each worker would keep its own counters and a scrape hitting one worker would
report only that worker's numbers.

To aggregate across workers the service uses `prometheus_client` **multiprocess
mode**, enabled when `PROMETHEUS_MULTIPROC_DIR` is set:

- Workers write per-process mmap files into that dir.
- `/metrics` builds a fresh `CollectorRegistry`, attaches a
  `MultiProcessCollector`, and sums every worker's series.
- `deploy/gunicorn.conf.py` manages the dir: `on_starting` wipes + recreates it
  (so a restart doesn't carry stale counters); `child_exit` calls
  `multiprocess.mark_process_dead(pid)` so a dead worker's files stop counting.
- systemd provides the dir via `RuntimeDirectory=data-analysis` +
  `Environment=PROMETHEUS_MULTIPROC_DIR=/run/data-analysis/prometheus`
  (tmpfs, wiped on restart).

When `PROMETHEUS_MULTIPROC_DIR` is **unset** (e.g. `flask run` in dev) the app
falls back to the plain in-process default registry.

> **Caveat:** in multiprocess mode `MultiProcessCollector` does **not** export
> the default `process_*`, `python_gc_*`, or `python_info` series — that is a
> `prometheus_client` limitation. Those appear only in single-process/dev mode.
> The custom `http_*` metrics below are exported in both modes.

---

## HTTP metrics

Emitted by the `before_request`/`after_request` hooks (`app/metrics.py`) on
every request except `/metrics`. The `path` label is the **matched route rule**,
not the raw URL — routes carry no path params, so the rule equals the concrete
path and cardinality stays bounded. Requests that match no route collapse to
`path="__unmatched__"` so 404 spam can't blow up cardinality.

### `http_requests_total` — Counter

Total HTTP requests processed.

| Label | Meaning | Example |
|-------|---------|---------|
| `method` | HTTP verb | `GET`, `POST` |
| `path` | matched route rule | `/analysis/health`, `/analysis/outliers`, `__unmatched__` |
| `status` | HTTP status code | `200`, `400`, `500` |

### `http_request_duration_seconds` — Histogram

HTTP request latency in seconds.

| Label | Meaning |
|-------|---------|
| `method` | HTTP verb |
| `path` | matched route rule |

Exposed series (per label set): `..._bucket{le=...}`, `..._sum`, `..._count`.
Buckets = `prometheus_client` defaults
(`.005 .01 .025 .05 .075 .1 .25 .5 .75 1 2.5 5 7.5 10 +Inf`).

**Instrumented paths:** `/analysis/health`, `/analysis/methods`,
`/analysis/outliers`, `/analysis/denoise`, `/analysis/regression`,
`/analysis/predict` (whatever gets hit; `/metrics` excluded). Paths shift if
`ANALYSIS__ROUTE_PREFIX` is set.

---

## Default (process / runtime) metrics

Auto-exported by `prometheus_client` on the default registry — no app code.
**Present only in single-process/dev mode** (see the multiprocess caveat above):

- `process_*` — e.g. `process_resident_memory_bytes`, `process_cpu_seconds_total`,
  `process_open_fds`, `process_start_time_seconds`.
- `python_gc_*` — `python_gc_objects_collected_total`,
  `python_gc_collections_total`, etc.
- `python_info{version=...,implementation=...}` — build info.

---

## Sample scrape (abridged)

```text
# HELP http_requests_total Total HTTP requests processed.
# TYPE http_requests_total counter
http_requests_total{method="POST",path="/analysis/outliers",status="200"} 12.0
http_requests_total{method="GET",path="/analysis/health",status="200"} 340.0

# HELP http_request_duration_seconds HTTP request latency in seconds.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="POST",path="/analysis/outliers",le="0.1"} 9.0
http_request_duration_seconds_bucket{method="POST",path="/analysis/outliers",le="+Inf"} 12.0
http_request_duration_seconds_sum{method="POST",path="/analysis/outliers"} 1.83
http_request_duration_seconds_count{method="POST",path="/analysis/outliers"} 12.0
```
