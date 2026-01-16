"""
Delta-based Strike Selection for Wheel Strategy

Finds optimal strikes for selling puts and calls based on target delta,
DTE range, and minimum premium requirements.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from qwen.data.base import DataProvider, OptionContract
from qwen.data.yahoo import YahooDataProvider
from qwen.pricing.black_scholes import BlackScholes

logger = logging.getLogger(__name__)


@dataclass
class StrikeCandidate:
    """A potential strike for the wheel strategy."""

    contract: OptionContract
    delta: float
    theoretical_price: float
    days_to_expiration: int
    annualized_return: float  # ROI annualized
    premium_return: float  # Premium / collateral

    @property
    def is_put(self) -> bool:
        return self.contract.option_type == "put"

    @property
    def is_call(self) -> bool:
        return self.contract.option_type == "call"


class StrikeSelector:
    """
    Selects optimal strikes for wheel strategy based on delta targeting.

    Uses Black-Scholes to calculate theoretical deltas and find strikes
    that match the target delta within the specified DTE range.
    """

    def __init__(
        self,
        data_provider: Optional[DataProvider] = None,
        risk_free_rate: float = 0.05,
    ):
        """
        Initialize the strike selector.

        Args:
            data_provider: Market data provider (defaults to Yahoo)
            risk_free_rate: Risk-free rate for pricing (default 5%)
        """
        self.provider = data_provider or YahooDataProvider()
        self.risk_free_rate = risk_free_rate

    def _get_current_price(self, symbol: str) -> float:
        """Get current stock price."""
        quote = self.provider.get_quote(symbol)
        return quote.last

    def _calculate_delta(
        self,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str,
    ) -> float:
        """
        Calculate theoretical delta using Black-Scholes.

        Args:
            spot: Current stock price
            strike: Strike price
            dte: Days to expiration
            iv: Implied volatility (decimal)
            option_type: 'put' or 'call'

        Returns:
            Delta value
        """
        time_to_expiry = dte / 365.0

        if time_to_expiry <= 0:
            # Expired - intrinsic only
            if option_type == "call":
                return 1.0 if spot > strike else 0.0
            else:
                return -1.0 if spot < strike else 0.0

        bs = BlackScholes(
            spot=spot,
            strike=strike,
            rate=self.risk_free_rate,
            volatility=iv,
            time_to_expiry=time_to_expiry,
        )

        return bs.delta(option_type)

    def _calculate_theoretical_price(
        self,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str,
    ) -> float:
        """Calculate theoretical option price using Black-Scholes."""
        time_to_expiry = dte / 365.0

        if time_to_expiry <= 0:
            if option_type == "call":
                return max(0, spot - strike)
            else:
                return max(0, strike - spot)

        bs = BlackScholes(
            spot=spot,
            strike=strike,
            rate=self.risk_free_rate,
            volatility=iv,
            time_to_expiry=time_to_expiry,
        )

        return bs.price(option_type)

    def _filter_by_dte(
        self,
        expirations: list[datetime],
        min_dte: int,
        max_dte: int,
    ) -> list[datetime]:
        """Filter expirations to those within DTE range."""
        today = datetime.now().date()
        valid = []

        for exp in expirations:
            exp_date = exp.date() if isinstance(exp, datetime) else exp
            dte = (exp_date - today).days

            if min_dte <= dte <= max_dte:
                valid.append(exp)

        return valid

    def _score_candidate(
        self,
        candidate: StrikeCandidate,
        target_delta: float,
        prefer_higher_premium: bool = True,
    ) -> float:
        """
        Score a strike candidate for selection.

        Lower score is better.
        """
        # Delta distance from target (primary factor)
        delta_distance = abs(abs(candidate.delta) - abs(target_delta))

        # Premium factor (higher is better)
        premium_factor = -candidate.premium_return if prefer_higher_premium else 0

        # Combine factors (delta match is most important)
        return delta_distance * 10 + premium_factor

    def find_put_strike(
        self,
        symbol: str,
        target_delta: float = -0.25,
        min_dte: int = 25,
        max_dte: int = 45,
        min_premium: float = 0.30,
        min_open_interest: int = 10,
    ) -> Optional[StrikeCandidate]:
        """
        Find optimal put strike for selling cash-secured puts.

        Args:
            symbol: Stock ticker
            target_delta: Target delta (negative for puts, e.g., -0.25 for 25-delta)
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            min_premium: Minimum premium per share
            min_open_interest: Minimum open interest for liquidity

        Returns:
            Best StrikeCandidate or None if nothing suitable found
        """
        logger.info(f"Finding put strike for {symbol}: delta={target_delta}, DTE={min_dte}-{max_dte}")

        # Get current price
        spot = self._get_current_price(symbol)
        logger.debug(f"{symbol} current price: ${spot:.2f}")

        # Get available expirations
        expirations = self.provider.get_expirations(symbol)
        valid_expirations = self._filter_by_dte(expirations, min_dte, max_dte)

        if not valid_expirations:
            logger.warning(f"No expirations found in {min_dte}-{max_dte} DTE range")
            return None

        logger.debug(f"Found {len(valid_expirations)} valid expirations")

        candidates = []

        for exp in valid_expirations:
            chain = self.provider.get_options_chain(symbol, exp)
            puts = [c for c in chain if c.option_type == "put"]

            today = datetime.now().date()
            exp_date = exp.date() if isinstance(exp, datetime) else exp
            dte = (exp_date - today).days

            for contract in puts:
                # Skip illiquid contracts
                if contract.open_interest < min_open_interest:
                    continue

                # Skip if premium too low
                premium = contract.mid
                if premium < min_premium:
                    continue

                # Calculate delta
                iv = contract.implied_volatility or 0.30  # Default IV if missing
                delta = self._calculate_delta(spot, contract.strike, dte, iv, "put")

                # Skip if delta is too far from target (OTM puts have negative delta)
                if abs(delta) > 0.50:  # Skip ITM puts
                    continue

                # Calculate returns
                collateral = contract.strike * 100  # Cash needed for 1 CSP
                premium_total = premium * 100
                premium_return = premium_total / collateral
                annualized_return = premium_return * (365 / dte) if dte > 0 else 0

                theoretical_price = self._calculate_theoretical_price(
                    spot, contract.strike, dte, iv, "put"
                )

                candidate = StrikeCandidate(
                    contract=contract,
                    delta=delta,
                    theoretical_price=theoretical_price,
                    days_to_expiration=dte,
                    annualized_return=annualized_return,
                    premium_return=premium_return,
                )
                candidates.append(candidate)

        if not candidates:
            logger.warning(f"No suitable put candidates found for {symbol}")
            return None

        # Sort by score (delta match + premium)
        candidates.sort(key=lambda c: self._score_candidate(c, target_delta))

        best = candidates[0]
        logger.info(
            f"Selected put: {best.contract.symbol} "
            f"strike=${best.contract.strike:.2f}, "
            f"delta={best.delta:.3f}, "
            f"premium=${best.contract.mid:.2f}, "
            f"DTE={best.days_to_expiration}, "
            f"annual ROI={best.annualized_return:.1%}"
        )

        return best

    def find_call_strike(
        self,
        symbol: str,
        cost_basis: float,
        target_delta: float = 0.30,
        min_dte: int = 25,
        max_dte: int = 45,
        min_premium: float = 0.20,
        min_open_interest: int = 10,
    ) -> Optional[StrikeCandidate]:
        """
        Find optimal call strike for selling covered calls.

        Args:
            symbol: Stock ticker
            cost_basis: Cost basis per share (won't sell below this)
            target_delta: Target delta (positive for calls, e.g., 0.30 for 30-delta)
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            min_premium: Minimum premium per share
            min_open_interest: Minimum open interest for liquidity

        Returns:
            Best StrikeCandidate or None if nothing suitable found
        """
        logger.info(
            f"Finding call strike for {symbol}: "
            f"cost_basis=${cost_basis:.2f}, delta={target_delta}, DTE={min_dte}-{max_dte}"
        )

        # Get current price
        spot = self._get_current_price(symbol)
        logger.debug(f"{symbol} current price: ${spot:.2f}")

        # Get available expirations
        expirations = self.provider.get_expirations(symbol)
        valid_expirations = self._filter_by_dte(expirations, min_dte, max_dte)

        if not valid_expirations:
            logger.warning(f"No expirations found in {min_dte}-{max_dte} DTE range")
            return None

        candidates = []

        for exp in valid_expirations:
            chain = self.provider.get_options_chain(symbol, exp)
            calls = [c for c in chain if c.option_type == "call"]

            today = datetime.now().date()
            exp_date = exp.date() if isinstance(exp, datetime) else exp
            dte = (exp_date - today).days

            for contract in calls:
                # Skip illiquid contracts
                if contract.open_interest < min_open_interest:
                    continue

                # Skip if below cost basis (never sell below cost!)
                if contract.strike < cost_basis:
                    continue

                # Skip if premium too low
                premium = contract.mid
                if premium < min_premium:
                    continue

                # Calculate delta
                iv = contract.implied_volatility or 0.30
                delta = self._calculate_delta(spot, contract.strike, dte, iv, "call")

                # Skip ITM calls (delta > 0.50)
                if delta > 0.50:
                    continue

                # Calculate returns
                # For covered calls, collateral is the stock value
                collateral = spot * 100
                premium_total = premium * 100
                premium_return = premium_total / collateral
                annualized_return = premium_return * (365 / dte) if dte > 0 else 0

                theoretical_price = self._calculate_theoretical_price(
                    spot, contract.strike, dte, iv, "call"
                )

                candidate = StrikeCandidate(
                    contract=contract,
                    delta=delta,
                    theoretical_price=theoretical_price,
                    days_to_expiration=dte,
                    annualized_return=annualized_return,
                    premium_return=premium_return,
                )
                candidates.append(candidate)

        if not candidates:
            logger.warning(f"No suitable call candidates found for {symbol}")
            return None

        # Sort by score
        candidates.sort(key=lambda c: self._score_candidate(c, target_delta))

        best = candidates[0]
        logger.info(
            f"Selected call: {best.contract.symbol} "
            f"strike=${best.contract.strike:.2f}, "
            f"delta={best.delta:.3f}, "
            f"premium=${best.contract.mid:.2f}, "
            f"DTE={best.days_to_expiration}, "
            f"annual ROI={best.annualized_return:.1%}"
        )

        return best

    def analyze_wheel_opportunity(
        self,
        symbol: str,
        target_put_delta: float = -0.25,
        target_call_delta: float = 0.30,
        min_dte: int = 25,
        max_dte: int = 45,
    ) -> dict:
        """
        Analyze complete wheel opportunity for a symbol.

        Returns analysis of both put and call opportunities.
        """
        spot = self._get_current_price(symbol)

        put = self.find_put_strike(
            symbol,
            target_delta=target_put_delta,
            min_dte=min_dte,
            max_dte=max_dte,
        )

        # For call analysis, assume we'd be assigned at the put strike
        hypothetical_cost_basis = put.contract.strike - put.contract.mid if put else spot

        call = self.find_call_strike(
            symbol,
            cost_basis=hypothetical_cost_basis,
            target_delta=target_call_delta,
            min_dte=min_dte,
            max_dte=max_dte,
        )

        return {
            "symbol": symbol,
            "current_price": spot,
            "put_opportunity": {
                "strike": put.contract.strike if put else None,
                "premium": put.contract.mid if put else None,
                "delta": put.delta if put else None,
                "dte": put.days_to_expiration if put else None,
                "annualized_roi": put.annualized_return if put else None,
                "contract_symbol": put.contract.symbol if put else None,
            } if put else None,
            "call_opportunity": {
                "strike": call.contract.strike if call else None,
                "premium": call.contract.mid if call else None,
                "delta": call.delta if call else None,
                "dte": call.days_to_expiration if call else None,
                "annualized_roi": call.annualized_return if call else None,
                "contract_symbol": call.contract.symbol if call else None,
            } if call else None,
            "estimated_wheel_return": (
                (put.annualized_return + (call.annualized_return if call else 0)) / 2
                if put else None
            ),
        }
