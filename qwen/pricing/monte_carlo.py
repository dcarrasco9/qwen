"""Monte Carlo option pricing model."""

import numpy as np
from typing import Literal, Optional
from dataclasses import dataclass


@dataclass
class MonteCarloResult:
    """Result from Monte Carlo simulation."""

    price: float
    std_error: float
    confidence_interval: tuple[float, float]  # 95% CI
    paths_simulated: int


class MonteCarlo:
    """
    Monte Carlo simulation for option pricing.

    Advantages:
    - Can price complex/exotic options
    - Handles path-dependent payoffs
    - Provides confidence intervals
    - Easily extensible to multi-asset options
    """

    def __init__(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        num_paths: int = 10000,
        num_steps: int = 252,
        dividend_yield: float = 0.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize Monte Carlo pricer.

        Args:
            spot: Current price of the underlying
            strike: Strike price of the option
            rate: Risk-free interest rate (annualized, decimal)
            volatility: Volatility (annualized, decimal)
            time_to_expiry: Time to expiration in years
            num_paths: Number of simulation paths
            num_steps: Number of time steps per path
            dividend_yield: Continuous dividend yield (decimal)
            seed: Random seed for reproducibility
        """
        self.S = spot
        self.K = strike
        self.r = rate
        self.sigma = volatility
        self.T = time_to_expiry
        self.num_paths = num_paths
        self.num_steps = num_steps
        self.q = dividend_yield

        if seed is not None:
            np.random.seed(seed)

    def _simulate_paths(self, antithetic: bool = True) -> np.ndarray:
        """
        Simulate price paths using Geometric Brownian Motion.

        Args:
            antithetic: Use antithetic variates for variance reduction

        Returns:
            Array of shape (num_paths, num_steps + 1) with price paths
        """
        dt = self.T / self.num_steps
        drift = (self.r - self.q - 0.5 * self.sigma**2) * dt
        vol = self.sigma * np.sqrt(dt)

        if antithetic:
            # Generate half the paths, then mirror them
            half_paths = self.num_paths // 2
            Z = np.random.standard_normal((half_paths, self.num_steps))
            Z = np.vstack([Z, -Z])  # Antithetic pairs
        else:
            Z = np.random.standard_normal((self.num_paths, self.num_steps))

        # Cumulative sum for GBM
        log_returns = drift + vol * Z
        log_paths = np.cumsum(log_returns, axis=1)

        # Prepend initial price
        paths = np.zeros((self.num_paths, self.num_steps + 1))
        paths[:, 0] = self.S
        paths[:, 1:] = self.S * np.exp(log_paths)

        return paths

    def price(self, option_type: Literal["call", "put"] = "call") -> float:
        """
        Calculate option price.

        Args:
            option_type: 'call' or 'put'

        Returns:
            Option price
        """
        return self.price_with_stats(option_type).price

    def price_with_stats(
        self, option_type: Literal["call", "put"] = "call", antithetic: bool = True
    ) -> MonteCarloResult:
        """
        Calculate option price with statistics.

        Args:
            option_type: 'call' or 'put'
            antithetic: Use antithetic variates

        Returns:
            MonteCarloResult with price, std error, and confidence interval
        """
        if self.T <= 0:
            if option_type == "call":
                intrinsic = max(0, self.S - self.K)
            else:
                intrinsic = max(0, self.K - self.S)
            return MonteCarloResult(
                price=intrinsic,
                std_error=0,
                confidence_interval=(intrinsic, intrinsic),
                paths_simulated=0,
            )

        paths = self._simulate_paths(antithetic)
        terminal_prices = paths[:, -1]

        # Calculate payoffs
        if option_type == "call":
            payoffs = np.maximum(terminal_prices - self.K, 0)
        else:
            payoffs = np.maximum(self.K - terminal_prices, 0)

        # Discount to present value
        discount = np.exp(-self.r * self.T)
        pv_payoffs = discount * payoffs

        # Statistics
        price = np.mean(pv_payoffs)
        std = np.std(pv_payoffs, ddof=1)
        std_error = std / np.sqrt(self.num_paths)

        # 95% confidence interval
        z = 1.96
        ci_lower = price - z * std_error
        ci_upper = price + z * std_error

        return MonteCarloResult(
            price=price,
            std_error=std_error,
            confidence_interval=(ci_lower, ci_upper),
            paths_simulated=self.num_paths,
        )

    def call_price(self) -> float:
        """Calculate call option price."""
        return self.price("call")

    def put_price(self) -> float:
        """Calculate put option price."""
        return self.price("put")

    def delta(self, option_type: Literal["call", "put"] = "call", bump: float = 0.01) -> float:
        """
        Calculate delta using finite difference.

        Args:
            option_type: 'call' or 'put'
            bump: Percentage bump for finite difference

        Returns:
            Delta estimate
        """
        bump_amount = self.S * bump

        # Price with spot up
        mc_up = MonteCarlo(
            self.S + bump_amount,
            self.K,
            self.r,
            self.sigma,
            self.T,
            self.num_paths,
            self.num_steps,
            self.q,
        )
        price_up = mc_up.price(option_type)

        # Price with spot down
        mc_down = MonteCarlo(
            self.S - bump_amount,
            self.K,
            self.r,
            self.sigma,
            self.T,
            self.num_paths,
            self.num_steps,
            self.q,
        )
        price_down = mc_down.price(option_type)

        return (price_up - price_down) / (2 * bump_amount)

    def gamma(self, option_type: Literal["call", "put"] = "call", bump: float = 0.01) -> float:
        """
        Calculate gamma using finite difference.

        Args:
            option_type: 'call' or 'put'
            bump: Percentage bump for finite difference

        Returns:
            Gamma estimate
        """
        bump_amount = self.S * bump

        # Delta with spot up
        mc_up = MonteCarlo(
            self.S + bump_amount,
            self.K,
            self.r,
            self.sigma,
            self.T,
            self.num_paths,
            self.num_steps,
            self.q,
        )
        delta_up = mc_up.delta(option_type)

        # Delta with spot down
        mc_down = MonteCarlo(
            self.S - bump_amount,
            self.K,
            self.r,
            self.sigma,
            self.T,
            self.num_paths,
            self.num_steps,
            self.q,
        )
        delta_down = mc_down.delta(option_type)

        return (delta_up - delta_down) / (2 * bump_amount)

    def price_asian(self, option_type: Literal["call", "put"] = "call") -> MonteCarloResult:
        """
        Price an Asian option (average price).

        Args:
            option_type: 'call' or 'put'

        Returns:
            MonteCarloResult for Asian option
        """
        if self.T <= 0:
            if option_type == "call":
                intrinsic = max(0, self.S - self.K)
            else:
                intrinsic = max(0, self.K - self.S)
            return MonteCarloResult(
                price=intrinsic,
                std_error=0,
                confidence_interval=(intrinsic, intrinsic),
                paths_simulated=0,
            )

        paths = self._simulate_paths()
        average_prices = np.mean(paths, axis=1)

        if option_type == "call":
            payoffs = np.maximum(average_prices - self.K, 0)
        else:
            payoffs = np.maximum(self.K - average_prices, 0)

        discount = np.exp(-self.r * self.T)
        pv_payoffs = discount * payoffs

        price = np.mean(pv_payoffs)
        std = np.std(pv_payoffs, ddof=1)
        std_error = std / np.sqrt(self.num_paths)

        z = 1.96
        ci_lower = price - z * std_error
        ci_upper = price + z * std_error

        return MonteCarloResult(
            price=price,
            std_error=std_error,
            confidence_interval=(ci_lower, ci_upper),
            paths_simulated=self.num_paths,
        )

    def price_barrier(
        self,
        option_type: Literal["call", "put"] = "call",
        barrier: float = None,
        barrier_type: Literal["up-and-out", "down-and-out", "up-and-in", "down-and-in"] = "down-and-out",
    ) -> MonteCarloResult:
        """
        Price a barrier option.

        Args:
            option_type: 'call' or 'put'
            barrier: Barrier level (default: 80% of spot for down, 120% for up)
            barrier_type: Type of barrier

        Returns:
            MonteCarloResult for barrier option
        """
        if barrier is None:
            if "down" in barrier_type:
                barrier = self.S * 0.8
            else:
                barrier = self.S * 1.2

        if self.T <= 0:
            if option_type == "call":
                intrinsic = max(0, self.S - self.K)
            else:
                intrinsic = max(0, self.K - self.S)
            return MonteCarloResult(
                price=intrinsic,
                std_error=0,
                confidence_interval=(intrinsic, intrinsic),
                paths_simulated=0,
            )

        paths = self._simulate_paths()
        terminal_prices = paths[:, -1]

        # Check barrier conditions
        if "down" in barrier_type:
            min_prices = np.min(paths, axis=1)
            barrier_hit = min_prices <= barrier
        else:
            max_prices = np.max(paths, axis=1)
            barrier_hit = max_prices >= barrier

        # Calculate vanilla payoffs
        if option_type == "call":
            vanilla_payoffs = np.maximum(terminal_prices - self.K, 0)
        else:
            vanilla_payoffs = np.maximum(self.K - terminal_prices, 0)

        # Apply barrier logic
        if "out" in barrier_type:
            payoffs = np.where(barrier_hit, 0, vanilla_payoffs)
        else:  # "in"
            payoffs = np.where(barrier_hit, vanilla_payoffs, 0)

        discount = np.exp(-self.r * self.T)
        pv_payoffs = discount * payoffs

        price = np.mean(pv_payoffs)
        std = np.std(pv_payoffs, ddof=1)
        std_error = std / np.sqrt(self.num_paths)

        z = 1.96
        ci_lower = price - z * std_error
        ci_upper = price + z * std_error

        return MonteCarloResult(
            price=price,
            std_error=std_error,
            confidence_interval=(ci_lower, ci_upper),
            paths_simulated=self.num_paths,
        )
