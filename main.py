from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any, Literal

import numpy as np
from dotenv import find_dotenv, load_dotenv
from flask import Flask, jsonify, request
from scipy.stats import norm

load_dotenv(find_dotenv(usecwd=True), override=False)


OutlierMethod = Literal["3sigma", "chauvenet", "iqr"]


def _bad_request(message: str, *, details: dict[str, Any] | None = None, status_code: int = 400):
    payload: dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def _parse_values(payload: dict[str, Any]) -> np.ndarray | tuple[Any, int]:
    if "values" not in payload:
        return _bad_request('Falta el campo "values" (lista numérica).')

    values = payload["values"]
    if not isinstance(values, list):
        return _bad_request('El campo "values" debe ser una lista.')
    if len(values) == 0:
        return _bad_request('El campo "values" no puede estar vacío.')

    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        return _bad_request('El campo "values" debe contener solo números.')

    if arr.ndim != 1:
        return _bad_request('El campo "values" debe ser una lista 1D.')
    if not np.isfinite(arr).all():
        return _bad_request('El campo "values" no puede contener NaN/Inf.')

    return arr


def _validate_timestamps(payload: dict[str, Any], n: int) -> tuple[Any, int] | None:
    if "timestamps" not in payload:
        return None

    timestamps = payload["timestamps"]
    if not isinstance(timestamps, list):
        return _bad_request('El campo "timestamps" debe ser una lista si se provee.')
    if len(timestamps) != n:
        return _bad_request(
            'La longitud de "timestamps" debe coincidir con la de "values".',
            details={"values_len": n, "timestamps_len": len(timestamps)},
        )
    return None


def _parse_method(payload: dict[str, Any]) -> OutlierMethod | tuple[Any, int]:
    method = payload.get("method")
    if not isinstance(method, str):
        return _bad_request('El campo "method" es obligatorio y debe ser string: "3sigma|chauvenet|iqr".')

    normalized = method.strip().lower()
    if normalized not in {"3sigma", "chauvenet", "iqr"}:
        return _bad_request(
            'Método inválido. Use "3sigma", "chauvenet" o "iqr".',
            details={"method": method},
        )
    if normalized == "3sigma":
        return "3sigma"
    if normalized == "chauvenet":
        return "chauvenet"
    return "iqr"


def _normalize_host(raw: str) -> str:
    candidate = raw.strip()
    if not candidate:
        return "0.0.0.0"
    if "://" in candidate:
        parsed = urlparse(candidate)
        if parsed.hostname:
            return "0.0.0.0"
    return candidate


def _outliers_3sigma(values: np.ndarray) -> tuple[list[int], dict[str, float]]:
    mean = float(values.mean())
    std = float(values.std(ddof=0))
    if std == 0.0:
        return [], {"mean": mean, "std": std, "lower": mean, "upper": mean, "k": 3.0}

    k = 3.0
    lower = mean - k * std
    upper = mean + k * std
    indices = np.where((values < lower) | (values > upper))[0].astype(int).tolist()
    return indices, {"mean": mean, "std": std, "lower": float(lower), "upper": float(upper), "k": k}


def _outliers_iqr(values: np.ndarray) -> tuple[list[int], dict[str, float]]:
    q1, q3 = np.percentile(values, [25, 75], method="linear")
    iqr = float(q3 - q1)
    k = 1.5
    lower = float(q1 - k * iqr)
    upper = float(q3 + k * iqr)
    indices = np.where((values < lower) | (values > upper))[0].astype(int).tolist()
    return indices, {"q1": float(q1), "q3": float(q3), "iqr": iqr, "lower": lower, "upper": upper, "k": k}


def _outliers_chauvenet(values: np.ndarray) -> tuple[list[int], dict[str, float]]:
    n = int(values.size)
    mean = float(values.mean())
    std = float(values.std(ddof=0))
    if std == 0.0:
        return [], {"n": float(n), "mean": mean, "std": std, "probability_cutoff": 0.0, "criterion": 0.5}

    z = np.abs((values - mean) / std)
    p_one_sided = (1.0 - norm.cdf(z)).astype(float)
    probability_cutoff = 0.5 / n
    indices = np.where(p_one_sided < probability_cutoff)[0].astype(int).tolist()

    max_z = float(np.max(z)) if n > 0 else 0.0
    return indices, {
        "n": float(n),
        "mean": mean,
        "std": std,
        "criterion": 0.5,
        "probability_cutoff": float(probability_cutoff),
        "max_abs_z": max_z,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "healthy", "service": "data-analysis", "version": "1.0.0"})

    @app.get("/analysis/methods")
    def analysis_methods():
        return jsonify(
            {
                "methods": [
                    {
                        "method": "3sigma",
                        "description": "Pauta criterion: outlier si value < μ - 3σ o value > μ + 3σ.",
                    },
                    {
                        "method": "chauvenet",
                        "description": "Chauvenet criterion: outlier si n * P < 0.5, con P = 1 - Φ(z).",
                    },
                    {
                        "method": "iqr",
                        "description": "IQR: outlier si value < Q1 - 1.5*IQR o value > Q3 + 1.5*IQR.",
                    },
                ]
            }
        )

    @app.post("/analysis/outliers")
    def analysis_outliers():
        if not request.is_json:
            return _bad_request("El cuerpo debe ser JSON.")

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _bad_request("JSON inválido: se esperaba un objeto.")

        parsed_values = _parse_values(payload)
        if isinstance(parsed_values, tuple):
            return parsed_values
        values = parsed_values

        ts_error = _validate_timestamps(payload, int(values.size))
        if ts_error is not None:
            return ts_error

        parsed_method = _parse_method(payload)
        if isinstance(parsed_method, tuple):
            return parsed_method
        method: OutlierMethod = parsed_method

        timestamps = payload.get("timestamps")
        if isinstance(timestamps, list):
            ts_list: list[Any] = timestamps
        else:
            ts_list = []

        n = int(values.size)
        mean = float(values.mean())
        std = float(values.std(ddof=0))

        if method == "3sigma":
            outlier_indices, threshold = _outliers_3sigma(values)
            outliers: list[dict[str, Any]] = []
            for idx in outlier_indices:
                v = float(values[idx])
                criterion = "exceeds_upper" if v > threshold["upper"] else "exceeds_lower"
                outliers.append(
                    {
                        "index": idx,
                        "timestamp": ts_list[idx] if idx < len(ts_list) else None,
                        "value": v,
                        "threshold_upper": threshold["upper"],
                        "threshold_lower": threshold["lower"],
                        "criterion": criterion,
                    }
                )
        elif method == "iqr":
            outlier_indices, threshold = _outliers_iqr(values)
            outliers = []
            for idx in outlier_indices:
                v = float(values[idx])
                criterion = "exceeds_upper" if v > threshold["upper"] else "exceeds_lower"
                outliers.append(
                    {
                        "index": idx,
                        "timestamp": ts_list[idx] if idx < len(ts_list) else None,
                        "value": v,
                        "threshold_upper": threshold["upper"],
                        "threshold_lower": threshold["lower"],
                        "criterion": criterion,
                    }
                )
        elif method == "chauvenet":
            outlier_indices, threshold = _outliers_chauvenet(values)
            outliers = []
            if std == 0.0:
                z_scores = np.zeros_like(values)
                p = np.ones_like(values)
            else:
                z_scores = np.abs((values - mean) / std)
                p = 1.0 - norm.cdf(z_scores)

            for idx in outlier_indices:
                outliers.append(
                    {
                        "index": idx,
                        "timestamp": ts_list[idx] if idx < len(ts_list) else None,
                        "value": float(values[idx]),
                        "criterion": "chauvenet",
                        "z_score": float(z_scores[idx]),
                        "probability": float(p[idx]),
                    }
                )
        else:
            return _bad_request("Método no soportado.", details={"method": method})

        return jsonify(
            {
                "method": method,
                "outliers": outliers,
                "statistics": {"mean": mean, "std": std, "n": n, "outlier_count": len(outliers)},
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("BIND_HOST") or _normalize_host(os.getenv("HOST", "0.0.0.0"))
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port)
