import pandas as pd

from qwen.dashboard_core import calculate_regime, summarize_metrics


def test_calculate_regime_thresholds():
    assert calculate_regime(0) == "Low"
    assert calculate_regime(19.9) == "Low"
    assert calculate_regime(20) == "Normal-Low"
    assert calculate_regime(39.9) == "Normal-Low"
    assert calculate_regime(40) == "Normal"
    assert calculate_regime(59.9) == "Normal"
    assert calculate_regime(60) == "Elevated"
    assert calculate_regime(79.9) == "Elevated"
    assert calculate_regime(80) == "Extreme"
    assert calculate_regime(100) == "Extreme"


def test_summarize_metrics_counts_and_average():
    df = pd.DataFrame(
        {
            "1D %": [1.0, -2.0, 0.0, 3.0],
            "IV %ile": [10, 50, 85, 20],
        }
    )
    metrics = summarize_metrics(df)

    assert metrics["gainers"] == 2
    assert metrics["losers"] == 1
    assert metrics["avg_change"] == 0.5
    assert metrics["high_iv"] == 1
    assert metrics["low_iv"] == 2
    assert metrics["symbols"] == 4
