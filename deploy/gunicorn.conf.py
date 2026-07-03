"""gunicorn config — prometheus_client multiprocess lifecycle.

With multiple workers each process keeps its own counters, so a scrape hitting
one worker would report only that worker's numbers. prometheus_client's
multiprocess mode fixes this: workers write mmap files into
PROMETHEUS_MULTIPROC_DIR and /metrics aggregates them across all workers.

- on_starting (master, before workers fork): wipe + recreate the dir so a
  restart doesn't sum stale counters from the previous run.
- child_exit: drop a dead worker's files so its counters stop being counted.

If PROMETHEUS_MULTIPROC_DIR is unset these hooks no-op and the app uses the
plain in-process registry.
"""
import os
import shutil

_MP_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")


def on_starting(server):
    if _MP_DIR:
        shutil.rmtree(_MP_DIR, ignore_errors=True)
        os.makedirs(_MP_DIR, exist_ok=True)


def child_exit(server, worker):
    if _MP_DIR:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
