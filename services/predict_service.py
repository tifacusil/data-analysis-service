from __future__ import annotations

from typing import Any, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd


PredictModel = Literal["arima", "gm11"]


def _validate_inputs(
    values: List[float],
    timestamps: List[str],
    model: str,
    horizon: int,
    arima_order: Optional[List[int]],
) -> tuple[np.ndarray, list[pd.Timestamp], PredictModel, int, Optional[Tuple[int, int, int]]]:
    if len(values) == 0:
        raise ValueError('"values" no puede estar vacío.')
    if len(values) != len(timestamps):
        raise ValueError('La longitud de "timestamps" debe coincidir con la de "values".')
    if horizon <= 0:
        raise ValueError('"horizon" debe ser un entero > 0.')

    normalized_model = model.strip().lower()
    if normalized_model not in {"arima", "gm11"}:
        raise ValueError('Modelo inválido. Use "arima" o "gm11".')

    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError('"values" debe ser una lista 1D.')
    if not np.isfinite(arr).all():
        raise ValueError('"values" no puede contener NaN/Inf.')

    ts = pd.to_datetime(timestamps, utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError('"timestamps" debe contener fechas válidas (ISO 8601).')
    ts_list = [pd.Timestamp(t) for t in ts.to_list()]

    order: Optional[Tuple[int, int, int]] = None
    if arima_order is not None:
        if not isinstance(arima_order, list) or len(arima_order) != 3:
            raise ValueError('"arima_order" debe ser una lista de 3 enteros: [p, d, q].')
        if any((not isinstance(x, int)) for x in arima_order):
            raise ValueError('"arima_order" debe contener enteros.')
        p, d, q = (int(arima_order[0]), int(arima_order[1]), int(arima_order[2]))
        if p < 0 or d < 0 or q < 0:
            raise ValueError('"arima_order" no puede contener valores negativos.')
        order = (p, d, q)

    return arr, ts_list, normalized_model, int(horizon), order  # type: ignore[return-value]


def _infer_step(timestamps: list[pd.Timestamp]) -> pd.Timedelta:
    if len(timestamps) < 2:
        return pd.Timedelta(days=1)
    diffs = np.diff(np.asarray([t.value for t in timestamps], dtype=np.int64))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return pd.Timedelta(days=1)
    step_ns = int(np.median(diffs))
    return pd.to_timedelta(step_ns, unit="ns")


def _format_ts(ts: pd.Timestamp) -> str:
    s = ts.isoformat()
    return s.replace("+00:00", "Z")


def _future_timestamps(timestamps: list[pd.Timestamp], horizon: int) -> list[str]:
    last = timestamps[-1]
    step = _infer_step(timestamps)
    return [_format_ts(last + step * i) for i in range(1, horizon + 1)]


def _predict_gm11(values: np.ndarray, horizon: int) -> tuple[np.ndarray, dict[str, Any]]:
    n = int(values.size)
    if n < 4:
        raise ValueError('GM(1,1) requiere al menos 4 puntos.')

    x0 = values.astype(float, copy=False)
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])

    B = np.column_stack((-z1, np.ones(n - 1, dtype=float)))
    Y = x0[1:].reshape(-1, 1)
    coeffs, _, _, _ = np.linalg.lstsq(B, Y, rcond=None)
    a = float(coeffs[0, 0])
    b = float(coeffs[1, 0])

    if abs(a) < 1e-12:
        predicted = np.repeat(x0[-1], horizon).astype(float, copy=False)
        return predicted, {"a": a, "b": b, "strategy": "flat_fallback"}

    def x1_hat(k: int) -> float:
        return (x0[0] - b / a) * float(np.exp(-a * (k - 1))) + b / a

    total_len = n + horizon
    x1h = np.asarray([x1_hat(k) for k in range(1, total_len + 1)], dtype=float)
    x0h = np.empty(total_len, dtype=float)
    x0h[0] = x0[0]
    x0h[1:] = x1h[1:] - x1h[:-1]

    future = x0h[n:]
    return future, {"a": a, "b": b}


def _predict_arima(
    values: np.ndarray,
    horizon: int,
    order: Tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    from statsmodels.tsa.arima.model import ARIMA

    y = values.astype(float, copy=False)
    model = ARIMA(
        y,
        order=order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fit = model.fit()
    forecast = fit.get_forecast(steps=horizon)
    mean = np.asarray(forecast.predicted_mean, dtype=float)
    ci = forecast.conf_int(alpha=0.05)
    lower = np.asarray(ci.iloc[:, 0], dtype=float)
    upper = np.asarray(ci.iloc[:, 1], dtype=float)
    return mean, lower, upper, {"order": list(order)}


def predict(
    values: List[float],
    timestamps: List[str],
    model: str,
    horizon: int,
    arima_order: Optional[List[int]] = None,
) -> dict:
    arr, ts_list, requested_model, horizon, order = _validate_inputs(
        values, timestamps, model, horizon, arima_order
    )

    n = int(arr.size)
    predicted_timestamps = _future_timestamps(ts_list, horizon)

    min_arima_len = 12
    if requested_model == "arima" and n < min_arima_len:
        gm_pred, params = _predict_gm11(arr, horizon)
        return {
            "predicted_values": gm_pred.tolist(),
            "predicted_timestamps": predicted_timestamps,
            "model": "gm11",
            "params": {
                "requested_model": requested_model,
                "reason": f"len(values)={n} < {min_arima_len}",
                **params,
            },
        }

    if requested_model == "gm11":
        gm_pred, params = _predict_gm11(arr, horizon)
        return {
            "predicted_values": gm_pred.tolist(),
            "predicted_timestamps": predicted_timestamps,
            "model": "gm11",
            "params": {
                "requested_model": requested_model,
                **params,
            },
        }

    used_order = order or (1, 1, 1)
    try:
        pred, lower, upper, params = _predict_arima(arr, horizon, used_order)
        return {
            "predicted_values": pred.tolist(),
            "predicted_timestamps": predicted_timestamps,
            "confidence_lower": lower.tolist(),
            "confidence_upper": upper.tolist(),
            "model": "arima",
            "params": {
                "requested_model": requested_model,
                **params,
            },
        }
    except Exception:
        gm_pred, params = _predict_gm11(arr, horizon)
        return {
            "predicted_values": gm_pred.tolist(),
            "predicted_timestamps": predicted_timestamps,
            "model": "gm11",
            "params": {
                "requested_model": requested_model,
                "reason": "arima_failed",
                **params,
            },
        }
