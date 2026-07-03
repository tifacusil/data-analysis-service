"""Prometheus instrumentation for the Flask HTTP app.

Single `/metrics` endpoint on the default `prometheus_client` registry. HTTP
requests are timed/counted via Flask `before_request`/`after_request` hooks.

Runs under gunicorn with multiple workers. When `PROMETHEUS_MULTIPROC_DIR` is
set, `prometheus_client` writes per-process mmap files there and `/metrics`
aggregates every worker via `MultiProcessCollector` (see `deploy/gunicorn.conf.py`
for the dir lifecycle). Without that env var (e.g. `flask run` in dev) it falls
back to the in-process default registry.
"""
from __future__ import annotations

import os
import time

from flask import Flask, Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

# Root path, no ROUTE_PREFIX: Prometheus kubernetes_sd / static scrape hits the
# pod port directly, not through the gateway.
METRICS_PATH = "/metrics"

# Fixed label for requests that matched no route, so 404 spam from arbitrary
# paths can't blow up label cardinality.
_UNMATCHED = "__unmatched__"

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests processed.",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)


def _label_path() -> str:
    """Matched route rule, not the raw URL — keeps cardinality bounded.

    These routes carry no path params, so the rule equals the concrete path
    (e.g. ``/analysis/outliers``). Unmatched requests collapse to a constant.
    """
    if request.url_rule is not None:
        return request.url_rule.rule
    return _UNMATCHED


def _before_request() -> None:
    g._metrics_start = time.perf_counter()


def _after_request(response: Response) -> Response:
    # Self-exclusion: scrapes must not inflate http_requests_total.
    if request.path == METRICS_PATH:
        return response

    method = request.method
    path = _label_path()

    start = g.pop("_metrics_start", None)
    if start is not None:
        http_request_duration_seconds.labels(method=method, path=path).observe(
            time.perf_counter() - start
        )
    http_requests_total.labels(
        method=method, path=path, status=str(response.status_code)
    ).inc()
    return response


def _metrics_endpoint() -> Response:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()
    # content_type (not mimetype): CONTENT_TYPE_LATEST already carries the
    # charset, so let Flask use it verbatim instead of appending another.
    return Response(data, content_type=CONTENT_TYPE_LATEST)


def init_metrics(app: Flask) -> None:
    """Register the HTTP hooks and the `/metrics` route on the Flask app."""
    app.before_request(_before_request)
    app.after_request(_after_request)
    app.add_url_rule(METRICS_PATH, "metrics", _metrics_endpoint, methods=["GET"])
