"""Binomial tree option pricing model."""

import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass


@dataclass
class BinomialResult:
    """Result from binomial tree pricing."""

    price: float
    delta: float
    gamma: float
    early_exercise_nodes: int  # Number of nodes where early exercise is optimal


class BinomialTree:
    """
    Cox-Ross-Rubinstein binomial tree option pricing model.

    Advantages over Black-Scholes:
    - Can price American options (early exercise)
    - Handles discrete dividends
    - Intuitive visualization of price paths
    """

    def __init__(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        steps: int = 100,
        dividend_yield: float = 0.0,
        american: bool = False,
    ):
        """
        Initialize binomial tree model.

        Args:
            spot: Current price of the underlying
            strike: Strike price of the option
            rate: Risk-free interest rate (annualized, decimal)
            volatility: Volatility (annualized, decimal)
            time_to_expiry: Time to expiration in years
            steps: Number of time steps in the tree
            dividend_yield: Continuous dividend yield (decimal)
            american: If True, allow early exercise (American option)
        """
        self.S = spot
        self.K = strike
        self.r = rate
        self.sigma = volatility
        self.T = time_to_expiry
        self.N = steps
        self.q = dividend_yield
        self.american = american

        # Compute tree parameters
        self._compute_parameters()

    def _compute_parameters(self):
        """Compute up/down factors and risk-neutral probability."""
        if self.T <= 0:
            self.dt = 0
            self.u = 1
            self.d = 1
            self.p = 0.5
            self.discount = 1
            return

        self.dt = self.T / self.N

        # CRR parameters
        self.u = np.exp(self.sigma * np.sqrt(self.dt))
        self.d = 1 / self.u

        # Risk-neutral probability
        a = np.exp((self.r - self.q) * self.dt)
        self.p = (a - self.d) / (self.u - self.d)

        # Discount factor per step
        self.discount = np.exp(-self.r * self.dt)

    def _build_price_tree(self) -> np.ndarray:
        """Build the stock price tree."""
        # Price at each node
        prices = np.zeros((self.N + 1, self.N + 1))

        for i in range(self.N + 1):
            for j in range(i + 1):
                prices[j, i] = self.S * (self.u ** (i - j)) * (self.d**j)

        return prices

    def price(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate option price.

        Args:
            option_type: 'call' or 'put'

        Returns:
            Option price
        """
        return self._price_tree(option_type).price

    def _price_tree(self, option_type: Literal["call", "put"] = "call") -> BinomialResult:
        """
        Build and price the full tree.

        Returns:
            BinomialResult with price and Greeks
        """
        if self.T <= 0:
            if option_type == "call":
                intrinsic = max(0, self.S - self.K)
            else:
                intrinsic = max(0, self.K - self.S)
            return BinomialResult(price=intrinsic, delta=0, gamma=0, early_exercise_nodes=0)

        # Build stock price tree
        stock_prices = self._build_price_tree()

        # Initialize option values at expiration
        option_values = np.zeros((self.N + 1, self.N + 1))
        early_exercise_count = 0

        # Terminal payoffs
        for j in range(self.N + 1):
            if option_type == "call":
                option_values[j, self.N] = max(0, stock_prices[j, self.N] - self.K)
            else:
                option_values[j, self.N] = max(0, self.K - stock_prices[j, self.N])

        # Backward induction
        for i in range(self.N - 1, -1, -1):
            for j in range(i + 1):
                # Expected value (risk-neutral)
                hold_value = self.discount * (
                    self.p * option_values[j, i + 1] + (1 - self.p) * option_values[j + 1, i + 1]
                )

                if self.american:
                    # Check early exercise
                    if option_type == "call":
                        exercise_value = max(0, stock_prices[j, i] - self.K)
                    else:
                        exercise_value = max(0, self.K - stock_prices[j, i])

                    if exercise_value > hold_value:
                        option_values[j, i] = exercise_value
                        early_exercise_count += 1
                    else:
                        option_values[j, i] = hold_value
                else:
                    option_values[j, i] = hold_value

        # Calculate Greeks from tree
        price = option_values[0, 0]

        # Delta: (f_u - f_d) / (S_u - S_d)
        if self.N >= 1:
            delta = (option_values[0, 1] - option_values[1, 1]) / (
                stock_prices[0, 1] - stock_prices[1, 1]
            )
        else:
            delta = 0

        # Gamma: rate of change of delta
        if self.N >= 2:
            delta_up = (option_values[0, 2] - option_values[1, 2]) / (
                stock_prices[0, 2] - stock_prices[1, 2]
            )
            delta_down = (option_values[1, 2] - option_values[2, 2]) / (
                stock_prices[1, 2] - stock_prices[2, 2]
            )
            gamma = (delta_up - delta_down) / (0.5 * (stock_prices[0, 2] - stock_prices[2, 2]))
        else:
            gamma = 0

        return BinomialResult(
            price=price, delta=delta, gamma=gamma, early_exercise_nodes=early_exercise_count
        )

    def call_price(self) -> float:
        """Calculate call option price."""
        return self.price("call")

    def put_price(self) -> float:
        """Calculate put option price."""
        return self.price("put")

    def delta(self, option_type: Literal["call", "put"] = "call") -> float:
        """Calculate delta from tree."""
        return self._price_tree(option_type).delta

    def gamma(self, option_type: Literal["call", "put"] = "call") -> float:
        """Calculate gamma from tree."""
        return self._price_tree(option_type).gamma

    def early_exercise_premium(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate early exercise premium (American - European value).

        Returns:
            Premium for early exercise ability
        """
        american = BinomialTree(
            self.S, self.K, self.r, self.sigma, self.T, self.N, self.q, american=True
        ).price(option_type)

        european = BinomialTree(
            self.S, self.K, self.r, self.sigma, self.T, self.N, self.q, american=False
        ).price(option_type)

        return american - european
