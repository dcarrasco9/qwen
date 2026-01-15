from __future__ import annotations

import pandas as pd


def calculate_regime(iv_percentile: float) -> str:
    if iv_percentile < 20:
        return "Low"
    if iv_percentile < 40:
        return "Normal-Low"
    if iv_percentile < 60:
        return "Normal"
    if iv_percentile < 80:
        return "Elevated"
    return "Extreme"


def summarize_metrics(df: pd.DataFrame) -> dict[str, float]:
    gainers = int((df["1D %"] > 0).sum())
    losers = int((df["1D %"] < 0).sum())
    avg_change = float(df["1D %"].mean()) if not df.empty else 0.0
    high_iv = int((df["IV %ile"] >= 80).sum())
    low_iv = int((df["IV %ile"] <= 20).sum())
    return {
        "gainers": gainers,
        "losers": losers,
        "avg_change": avg_change,
        "high_iv": high_iv,
        "low_iv": low_iv,
        "symbols": int(len(df)),
    }
