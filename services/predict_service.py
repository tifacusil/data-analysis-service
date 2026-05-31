import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA


def _future_timestamps(timestamps: list[str], horizon: int) -> list[str]:
    dt = pd.to_datetime(timestamps, utc=True)
    freq = None
    try:
        freq = pd.infer_freq(dt)
    except Exception:
        pass

    if freq is not None:
        future = pd.date_range(start=dt[-1], periods=horizon + 1, freq=freq)[1:]
    else:
        mean_delta = (dt[-1] - dt[0]) / max(len(dt) - 1, 1)
        future = pd.DatetimeIndex([dt[-1] + mean_delta * (i + 1) for i in range(horizon)])

    return [ts.isoformat() for ts in future]


def arima_predict(
    values: list[float],
    timestamps: list[str],
    horizon: int,
    order: tuple[int, int, int] = (1, 1, 1),
) -> dict:
    dt = pd.to_datetime(timestamps, utc=True)
    series = pd.Series(values, index=dt, dtype=float)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_fit = ARIMA(series, order=order).fit()
    except Exception as exc:
        raise ValueError(
            "ARIMA did not converge. Try a different order or use model=gm11 for short series."
        ) from exc

    forecast = model_fit.get_forecast(steps=horizon)
    frame = forecast.summary_frame(alpha=0.05)

    return {
        "predicted_values": frame["mean"].tolist(),
        "predicted_timestamps": _future_timestamps(timestamps, horizon),
        "confidence_lower": frame["mean_ci_lower"].tolist(),
        "confidence_upper": frame["mean_ci_upper"].tolist(),
        "model": "arima",
        "horizon": horizon,
        "order": list(order),
    }


def gm11_predict(
    values: list[float],
    timestamps: list[str],
    horizon: int,
) -> dict:
    if len(values) < 4:
        raise ValueError("gm11 requires at least 4 values")

    n = len(values)
    x0 = np.array(values, dtype=float)
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])  # n-1 elements

    B = np.column_stack([-z1, np.ones(n - 1)])
    Y = x0[1:]
    params, _, _, _ = np.linalg.lstsq(B, Y, rcond=None)
    a, b = params

    def x1_hat(k: float) -> float:
        return float((x0[0] - b / a) * np.exp(-a * (k - 1)) + b / a)

    # Future IAGO: x0_hat(n+j+1) = x1_hat(n+j+1) - x1_hat(n+j) for j=0..horizon-1
    predicted = [x1_hat(n + j + 1) - x1_hat(n + j) for j in range(horizon)]

    return {
        "predicted_values": predicted,
        "predicted_timestamps": _future_timestamps(timestamps, horizon),
        "confidence_lower": None,
        "confidence_upper": None,
        "model": "gm11",
        "horizon": horizon,
        "order": None,
    }
