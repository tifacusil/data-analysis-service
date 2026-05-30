from typing import List, Optional


def predict(
    values: List[float],
    timestamps: List[str],
    model: str,
    horizon: int,
    arima_order: Optional[List[int]] = None,
) -> dict:
    raise NotImplementedError("Card 4B2: Prediction not implemented")
