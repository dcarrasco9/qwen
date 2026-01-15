"""Black-Scholes option pricing model with Greeks."""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass
from typing import Literal


@dataclass
class Greeks:
    """Option Greeks (sensitivities)."""

    delta: float
    gamma: float
    theta: float  # Per day
    vega: float  # Per 1% vol change
    rho: float  # Per 1% rate change


class BlackScholes:
    """
    Black-Scholes-Merton option pricing model.

    Assumptions:
    - European-style options (no early exercise)
    - No dividends (or continuous dividend yield)
    - Constant volatility and risk-free rate
    - Lognormal distribution of returns
    """

    def __init__(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        dividend_yield: float = 0.0,
    ):
        """
        Initialize Black-Scholes model.

        Args:
            spot: Current price of the underlying
            strike: Strike price of the option
            rate: Risk-free interest rate (annualized, decimal)
            volatility: Implied volatility (annualized, decimal)
            time_to_expiry: Time to expiration in years
            dividend_yield: Continuous dividend yield (decimal)
        """
        self.S = spot
        self.K = strike
        self.r = rate
        self.sigma = volatility
        self.T = time_to_expiry
        self.q = dividend_yield

        # Pre-compute d1 and d2
        self._compute_d1_d2()

    def _compute_d1_d2(self):
        """Compute d1 and d2 parameters."""
        if self.T <= 0 or self.sigma <= 0:
            self._d1 = 0
            self._d2 = 0
            return

        sqrt_T = np.sqrt(self.T)
        self._d1 = (np.log(self.S / self.K) + (self.r - self.q + 0.5 * self.sigma**2) * self.T) / (
            self.sigma * sqrt_T
        )
        self._d2 = self._d1 - self.sigma * sqrt_T

    @property
    def d1(self) -> float:
        """d1 parameter."""
        return self._d1

    @property
    def d2(self) -> float:
        """d2 parameter."""
        return self._d2

    def call_price(self) -> float:
        """Calculate call option price."""
        if self.T <= 0:
            return max(0, self.S - self.K)

        return self.S * np.exp(-self.q * self.T) * norm.cdf(self.d1) - self.K * np.exp(
            -self.r * self.T
        ) * norm.cdf(self.d2)

    def put_price(self) -> float:
        """Calculate put option price."""
        if self.T <= 0:
            return max(0, self.K - self.S)

        return self.K * np.exp(-self.r * self.T) * norm.cdf(-self.d2) - self.S * np.exp(
            -self.q * self.T
        ) * norm.cdf(-self.d1)

    def price(self, option_type: Literal["call", "put"] = "call") -> float:
        """Calculate option price."""
        if option_type == "call":
            return self.call_price()
        return self.put_price()

    def delta(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate delta (sensitivity to underlying price).

        Returns:
            Delta value (call: 0 to 1, put: -1 to 0)
        """
        if self.T <= 0:
            if option_type == "call":
                return 1.0 if self.S > self.K else 0.0
            return -1.0 if self.S < self.K else 0.0

        exp_q = np.exp(-self.q * self.T)
        if option_type == "call":
            return exp_q * norm.cdf(self.d1)
        return -exp_q * norm.cdf(-self.d1)

    def gamma(self) -> float:
        """
        Calculate gamma (rate of change of delta).

        Returns:
            Gamma value (same for calls and puts)
        """
        if self.T <= 0 or self.sigma <= 0:
            return 0.0

        return (
            np.exp(-self.q * self.T)
            * norm.pdf(self.d1)
            / (self.S * self.sigma * np.sqrt(self.T))
        )

    def theta(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate theta (time decay) per calendar day.

        Returns:
            Theta value (typically negative)
        """
        if self.T <= 0:
            return 0.0

        sqrt_T = np.sqrt(self.T)
        exp_q = np.exp(-self.q * self.T)
        exp_r = np.exp(-self.r * self.T)

        # First term (common to both)
        term1 = -(self.S * exp_q * norm.pdf(self.d1) * self.sigma) / (2 * sqrt_T)

        if option_type == "call":
            term2 = -self.r * self.K * exp_r * norm.cdf(self.d2)
            term3 = self.q * self.S * exp_q * norm.cdf(self.d1)
        else:
            term2 = self.r * self.K * exp_r * norm.cdf(-self.d2)
            term3 = -self.q * self.S * exp_q * norm.cdf(-self.d1)

        # Return per-day theta (divide annual theta by 365)
        return (term1 + term2 + term3) / 365

    def vega(self) -> float:
        """
        Calculate vega (sensitivity to volatility).

        Returns:
            Vega value per 1% change in volatility
        """
        if self.T <= 0:
            return 0.0

        # Vega per 1% vol change (divide by 100)
        return self.S * np.exp(-self.q * self.T) * norm.pdf(self.d1) * np.sqrt(self.T) / 100

    def rho(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate rho (sensitivity to interest rate).

        Returns:
            Rho value per 1% change in rate
        """
        if self.T <= 0:
            return 0.0

        # Rho per 1% rate change (divide by 100)
        if option_type == "call":
            return self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(self.d2) / 100
        return -self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(-self.d2) / 100

    def greeks(self, option_type: Literal["call", "put"] = "call") -> Greeks:
        """
        Calculate all Greeks at once.

        Returns:
            Greeks dataclass with delta, gamma, theta, vega, rho
        """
        return Greeks(
            delta=self.delta(option_type),
            gamma=self.gamma(),
            theta=self.theta(option_type),
            vega=self.vega(),
            rho=self.rho(option_type),
        )

    def implied_volatility(
        self,
        market_price: float,
        option_type: Literal["call", "put"] = "call",
        tolerance: float = 1e-6,
        max_iterations: int = 100,
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson method.

        Args:
            market_price: Observed market price of the option
            option_type: 'call' or 'put'
            tolerance: Convergence tolerance
            max_iterations: Maximum iterations

        Returns:
            Implied volatility (annualized decimal)
        """
        # Initial guess using Brenner-Subrahmanyam approximation
        sigma = np.sqrt(2 * np.pi / self.T) * market_price / self.S

        for _ in range(max_iterations):
            bs = BlackScholes(self.S, self.K, self.r, sigma, self.T, self.q)
            price = bs.price(option_type)
            vega = bs.vega() * 100  # Convert back to raw vega

            diff = price - market_price

            if abs(diff) < tolerance:
                return sigma

            if vega < 1e-10:
                break

            sigma = sigma - diff / vega
            sigma = max(0.001, min(sigma, 5.0))  # Bound sigma

        return sigma


def call_price(spot: float, strike: float, rate: float, volatility: float, time_to_expiry: float) -> float:
    """Quick function to price a call option."""
    return BlackScholes(spot, strike, rate, volatility, time_to_expiry).call_price()


def put_price(spot: float, strike: float, rate: float, volatility: float, time_to_expiry: float) -> float:
    """Quick function to price a put option."""
    return BlackScholes(spot, strike, rate, volatility, time_to_expiry).put_price()
