"""
Volatility Analysis for Options Trading

Analyzes volatility regimes, term structure, and identifies
opportunities based on volatility patterns.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from qwen.data.base import DataProvider

logger = logging.getLogger(__name__)


@dataclass
class VolatilityRegime:
    """Current volatility regime assessment."""

    symbol: str
    current_iv: float
    realized_vol_20d: float
    realized_vol_60d: float
    iv_percentile: float  # 0-100, current IV vs past year
    vol_regime: str  # 'low', 'normal', 'elevated', 'extreme'
    recommendation: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class VolatilityAnalyzer:
    """
    Analyzes volatility patterns to identify trading opportunities.

    Key metrics:
    - IV Percentile: Where current IV ranks vs history
    - IV/RV Ratio: Implied vs realized volatility
    - Term Structure: Near vs far dated IV
    - Vol of Vol: Stability of volatility
    """

    def __init__(self, data_provider: DataProvider):
        self.provider = data_provider

    def analyze_symbol(self, symbol: str, lookback_days: int = 252) -> VolatilityRegime:
        """
        Comprehensive volatility analysis for a symbol.

        Args:
            symbol: Stock symbol
            lookback_days: Historical lookback for percentile calc

        Returns:
            VolatilityRegime assessment
        """
        end = datetime.now()
        start = end - timedelta(days=lookback_days + 60)

        history = self.provider.get_historical(symbol, start, end)

        if history.empty:
            raise ValueError(f"No data for {symbol}")

        # Calculate realized volatility
        returns = history['Close'].pct_change().dropna()

        rv_20d = returns.tail(20).std() * np.sqrt(252)
        rv_60d = returns.tail(60).std() * np.sqrt(252)

        # Calculate rolling 20-day realized vol for percentile
        rolling_vol = returns.rolling(20).std() * np.sqrt(252)
        rolling_vol = rolling_vol.dropna()

        current_rv = rolling_vol.iloc[-1]

        # Get IV from options chain
        try:
            chain = self.provider.get_options_chain(symbol)
            if chain:
                # Get ATM IV
                spot = history['Close'].iloc[-1]
                atm_options = [c for c in chain
                              if abs(c.strike - spot) / spot < 0.05
                              and c.implied_volatility]
                if atm_options:
                    current_iv = np.mean([c.implied_volatility for c in atm_options])
                else:
                    current_iv = current_rv * 1.1  # Estimate
            else:
                current_iv = current_rv * 1.1
        except Exception:
            current_iv = current_rv * 1.1

        # Calculate IV percentile (using RV as proxy if no historical IV)
        vol_percentile = (rolling_vol < current_rv).mean() * 100

        # Determine regime
        if vol_percentile < 20:
            regime = 'low'
            recommendation = "Consider buying options (cheap vol). Straddles, calendar spreads."
        elif vol_percentile < 40:
            regime = 'normal_low'
            recommendation = "Neutral to slightly long vol. Balanced strategies."
        elif vol_percentile < 60:
            regime = 'normal'
            recommendation = "No strong vol signal. Focus on directional views."
        elif vol_percentile < 80:
            regime = 'elevated'
            recommendation = "Consider selling premium. Iron condors, credit spreads."
        else:
            regime = 'extreme'
            recommendation = "High vol - consider selling puts on dips, or wait for vol crush."

        return VolatilityRegime(
            symbol=symbol,
            current_iv=current_iv,
            realized_vol_20d=rv_20d,
            realized_vol_60d=rv_60d,
            iv_percentile=vol_percentile,
            vol_regime=regime,
            recommendation=recommendation,
        )

    def calculate_vol_surface(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Calculate volatility surface (IV by strike and expiry).

        Returns:
            DataFrame with strike, expiry, IV, moneyness
        """
        # Get current price
        end = datetime.now()
        start = end - timedelta(days=5)
        history = self.provider.get_historical(symbol, start, end)
        spot = history['Close'].iloc[-1]

        # Get options chain
        chain = self.provider.get_options_chain(symbol)

        if not chain:
            return pd.DataFrame()

        data = []
        for opt in chain:
            if opt.implied_volatility:
                days_to_exp = (opt.expiration - datetime.now()).days
                if days_to_exp > 0:
                    data.append({
                        'strike': opt.strike,
                        'expiry': opt.expiration.strftime('%Y-%m-%d'),
                        'days_to_exp': days_to_exp,
                        'type': opt.option_type,
                        'iv': opt.implied_volatility,
                        'moneyness': opt.strike / spot,
                        'volume': opt.volume,
                        'open_interest': opt.open_interest,
                    })

        return pd.DataFrame(data)

    def find_vol_opportunities(
        self,
        symbols: list[str],
    ) -> pd.DataFrame:
        """
        Screen multiple symbols for volatility opportunities.

        Args:
            symbols: List of symbols to analyze

        Returns:
            DataFrame with vol metrics and recommendations
        """
        results = []

        for symbol in symbols:
            try:
                regime = self.analyze_symbol(symbol)
                results.append({
                    'symbol': symbol,
                    'current_iv': regime.current_iv,
                    'realized_20d': regime.realized_vol_20d,
                    'realized_60d': regime.realized_vol_60d,
                    'iv_rv_ratio': regime.current_iv / regime.realized_vol_20d if regime.realized_vol_20d > 0 else 0,
                    'iv_percentile': regime.iv_percentile,
                    'regime': regime.vol_regime,
                    'recommendation': regime.recommendation,
                })
            except Exception as e:
                logger.warning(f"Error analyzing {symbol}: {e}")

        df = pd.DataFrame(results)

        if not df.empty:
            df = df.sort_values('iv_percentile')

        return df

    def get_iv_term_structure(self, symbol: str) -> pd.DataFrame:
        """
        Analyze IV term structure (IV by expiration).

        Useful for calendar spread opportunities:
        - Normal: Far-dated IV > Near-dated IV (contango)
        - Inverted: Near-dated IV > Far-dated IV (backwardation)
        """
        vol_surface = self.calculate_vol_surface(symbol)

        if vol_surface.empty:
            return pd.DataFrame()

        # Group by expiry and calculate average ATM IV
        term_structure = vol_surface[
            (vol_surface['moneyness'] > 0.95) &
            (vol_surface['moneyness'] < 1.05)
        ].groupby('expiry').agg({
            'iv': 'mean',
            'days_to_exp': 'first',
            'volume': 'sum',
        }).reset_index()

        term_structure = term_structure.sort_values('days_to_exp')
        term_structure.columns = ['expiry', 'atm_iv', 'days_to_exp', 'total_volume']

        return term_structure


def calculate_iv_percentile(
    current_iv: float,
    historical_ivs: pd.Series,
) -> float:
    """
    Calculate where current IV ranks historically.

    Args:
        current_iv: Current implied volatility
        historical_ivs: Series of historical IV values

    Returns:
        Percentile (0-100)
    """
    return (historical_ivs < current_iv).mean() * 100
