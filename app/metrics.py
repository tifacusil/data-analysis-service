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

import psutil
from flask import Flask, Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_client.process_collector import ProcessCollector

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

# Buckets explicitos: sin esto, prometheus_client usa su default
# (.005 .01 .025 .05 .075 .1 .25 .5 .75 1 2.5 5 7.5 10), que no coincide con el
# SLO de Micrometer en data-management/project-management (5ms..1s) ni con los
# buckets del cliente Go en Sistema B. histogram_quantile interpola distinto
# segun los cortes del histograma, asi que percentiles con buckets distintos
# no son comparables aunque las muestras de origen sean identicas.
_HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    buckets=_HTTP_BUCKETS,
)

# prometheus_client auto-registers a ProcessCollector on import, exposing
# process_cpu_seconds_total / process_resident_memory_bytes on REGISTRY — but
# MultiProcessCollector excludes it, since it can't aggregate a "current value
# since start" across independent worker processes. Gunicorn always runs
# multi-worker in this deploy (see gunicorn.conf.py), so without a replacement
# the service would report zero process-level CPU/memory, breaking the
# Go-vs-Python comparison in the benchmark dashboard.
#
# Unregister the built-in collector and read the same metric names via psutil
# instead, so both single-process and multiprocess mode report consistently.
# multiprocess_mode="liveall" makes prometheus_client tag each worker's series
# with its own {pid=...} label rather than trying to sum them, so a scrape
# reflects only workers currently alive.
for _collector in list(REGISTRY._collector_to_names):
    if isinstance(_collector, ProcessCollector):
        REGISTRY.unregister(_collector)

_process_cpu_seconds = Gauge(
    "process_cpu_seconds_total",
    "Total user and system CPU time spent by this worker process, in seconds.",
    multiprocess_mode="liveall",
)
_process_resident_memory = Gauge(
    "process_resident_memory_bytes",
    "Resident memory size of this worker process, in bytes.",
    multiprocess_mode="liveall",
)


def _sample_process_metrics() -> None:
    proc = psutil.Process()
    cpu_times = proc.cpu_times()
    _process_cpu_seconds.set(cpu_times.user + cpu_times.system)
    _process_resident_memory.set(proc.memory_info().rss)


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
    _sample_process_metrics()
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
