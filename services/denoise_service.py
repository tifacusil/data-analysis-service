from __future__ import annotations

from typing import Any, List, Literal

import numpy as np


DenoiseMethod = Literal["wavelet", "emd", "svm"]


def _validate_inputs(values: List[float], timestamps: List[str], method: str) -> tuple[np.ndarray, DenoiseMethod]:
    if len(values) == 0:
        raise ValueError('"values" no puede estar vacío.')
    if len(values) != len(timestamps):
        raise ValueError('La longitud de "timestamps" debe coincidir con la de "values".')

    normalized = method.strip().lower()
    if normalized not in {"wavelet", "emd", "svm"}:
        raise ValueError('Método inválido. Use "wavelet", "emd" o "svm".')

    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError('"values" debe ser una lista 1D.')
    if not np.isfinite(arr).all():
        raise ValueError('"values" no puede contener NaN/Inf.')

    return arr, normalized  # type: ignore[return-value]


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    n = int(values.size)
    if n == 0:
        return values.copy()
    w = int(min(max(int(window), 1), n))
    kernel = np.ones(w, dtype=float) / float(w)
    return np.convolve(values, kernel, mode="same").astype(float, copy=False)


def _denoise_wavelet(values: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        import pywt
    except ModuleNotFoundError:
        window = 5
        denoised = _moving_average(values, window=window)
        return denoised, {"fallback": "moving_average", "window": int(min(window, int(values.size)))}

    n = int(values.size)
    if n < 4:
        return values.copy(), {"wavelet": None, "level": 0, "threshold": 0.0, "mode": "soft", "sigma": 0.0}

    wavelet_name = "db4"
    mode = "soft"

    wavelet = pywt.Wavelet(wavelet_name)
    max_level = int(pywt.dwt_max_level(n, wavelet.dec_len))
    level = min(4, max_level) if max_level > 0 else 0
    if level == 0:
        return values.copy(), {"wavelet": wavelet_name, "level": 0, "threshold": 0.0, "mode": mode, "sigma": 0.0}

    coeffs = pywt.wavedec(values, wavelet_name, level=level)
    finest_detail = coeffs[-1]
    if finest_detail.size == 0:
        sigma = 0.0
    else:
        sigma = float(np.median(np.abs(finest_detail)) / 0.6745)

    threshold = float(sigma * np.sqrt(2.0 * np.log(n))) if sigma > 0.0 else 0.0
    new_coeffs = [coeffs[0]] + [pywt.threshold(c, threshold, mode=mode) for c in coeffs[1:]]
    reconstructed = pywt.waverec(new_coeffs, wavelet_name)
    denoised = reconstructed[:n].astype(float, copy=False)
    return denoised, {"wavelet": wavelet_name, "level": level, "threshold": threshold, "mode": mode, "sigma": sigma}


def _zero_crossing_rate(x: np.ndarray) -> float:
    n = int(x.size)
    if n < 2:
        return 0.0
    crossings = np.sum(x[:-1] * x[1:] < 0.0)
    return float(crossings / (n - 1))


def _denoise_emd(values: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        from PyEMD import EMD
    except ModuleNotFoundError:
        window = 7
        denoised = _moving_average(values, window=window)
        return denoised, {"fallback": "moving_average", "window": int(min(window, int(values.size)))}

    n = int(values.size)
    if n < 4:
        return values.copy(), {"imf_count": 0, "removed_imfs": [], "strategy": "zcr_quantile", "quantile": 0.8}

    emd = EMD()
    imfs = emd.emd(values)
    if imfs is None or imfs.size == 0:
        return values.copy(), {"imf_count": 0, "removed_imfs": [], "strategy": "zcr_quantile", "quantile": 0.8}

    imf_count = int(imfs.shape[0])
    zcrs = np.asarray([_zero_crossing_rate(imfs[i]) for i in range(imf_count)], dtype=float)

    quantile = 0.8
    cutoff = float(np.quantile(zcrs, quantile)) if imf_count > 1 else float(zcrs[0])
    removed = np.where(zcrs >= cutoff)[0].astype(int).tolist()
    if imf_count > 1 and len(removed) == 0:
        removed = [int(np.argmax(zcrs))]
    if len(removed) >= imf_count:
        removed = removed[:-1]

    keep_mask = np.ones(imf_count, dtype=bool)
    keep_mask[removed] = False

    residue = values - imfs.sum(axis=0)
    kept_sum = imfs[keep_mask].sum(axis=0) if keep_mask.any() else np.zeros(n, dtype=float)
    denoised = (residue + kept_sum).astype(float, copy=False)

    return denoised, {
        "imf_count": imf_count,
        "removed_imfs": removed,
        "strategy": "zcr_quantile",
        "quantile": quantile,
        "zcrs": zcrs.tolist(),
    }


def _denoise_svm(values: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVR
    except ModuleNotFoundError:
        window = 5
        denoised = _moving_average(values, window=window)
        return denoised, {"fallback": "moving_average", "window": int(min(window, int(values.size)))}

    n = int(values.size)
    if n < 2:
        return values.copy(), {"kernel": "rbf", "C": None, "epsilon": None, "gamma": "scale", "feature": "index"}

    x = np.arange(n, dtype=float).reshape(-1, 1)
    y = values.astype(float, copy=False)

    y_std = float(np.std(y))
    epsilon = float(0.1 * y_std) if y_std > 0.0 else 0.1
    C = 10.0
    gamma: str | float = "scale"
    kernel = "rbf"

    model = Pipeline(
        [
            ("x_scaler", StandardScaler()),
            ("svr", SVR(kernel=kernel, C=C, epsilon=epsilon, gamma=gamma)),
        ]
    )
    model.fit(x, y)
    denoised = model.predict(x).astype(float, copy=False)
    return denoised, {"kernel": kernel, "C": C, "epsilon": epsilon, "gamma": gamma, "feature": "index"}


def denoise(
    values: List[float],
    timestamps: List[str],
    method: str,
) -> dict:
    arr, normalized_method = _validate_inputs(values, timestamps, method)

    if normalized_method == "wavelet":
        denoised, params = _denoise_wavelet(arr)
    elif normalized_method == "emd":
        denoised, params = _denoise_emd(arr)
    else:
        denoised, params = _denoise_svm(arr)

    return {
        "denoised_values": denoised.tolist(),
        "method": normalized_method,
        "params": params,
    }
