"""Tests for options pricing models."""

import pytest
import numpy as np
from qwen.pricing import BlackScholes, BinomialTree, MonteCarlo


class TestBlackScholes:
    """Tests for Black-Scholes model."""

    def test_call_price_atm(self):
        """Test ATM call pricing."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        price = bs.call_price()
        # ATM call with these params should be around $10.45
        assert 10 < price < 11

    def test_put_price_atm(self):
        """Test ATM put pricing."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        price = bs.put_price()
        # ATM put should be less than call due to forward
        assert 5 < price < 7

    def test_put_call_parity(self):
        """Test put-call parity: C - P = S - K*exp(-rT)."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0
        bs = BlackScholes(spot, strike, rate, vol, time)

        call = bs.call_price()
        put = bs.put_price()

        # Put-call parity
        parity_diff = call - put - (spot - strike * np.exp(-rate * time))
        assert abs(parity_diff) < 0.001

    def test_delta_call_bounds(self):
        """Test that call delta is between 0 and 1."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        delta = bs.delta("call")
        assert 0 < delta < 1

    def test_delta_put_bounds(self):
        """Test that put delta is between -1 and 0."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        delta = bs.delta("put")
        assert -1 < delta < 0

    def test_gamma_positive(self):
        """Test that gamma is always positive."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        gamma = bs.gamma()
        assert gamma > 0

    def test_theta_negative_for_long(self):
        """Test that theta is negative for long options."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        theta_call = bs.theta("call")
        # Theta should be negative (time decay)
        assert theta_call < 0

    def test_vega_positive(self):
        """Test that vega is positive."""
        bs = BlackScholes(spot=100, strike=100, rate=0.05, volatility=0.20, time_to_expiry=1.0)
        vega = bs.vega()
        assert vega > 0

    def test_expired_option_call_itm(self):
        """Test expired ITM call returns intrinsic value."""
        bs = BlackScholes(spot=110, strike=100, rate=0.05, volatility=0.20, time_to_expiry=0)
        assert bs.call_price() == 10

    def test_expired_option_call_otm(self):
        """Test expired OTM call returns zero."""
        bs = BlackScholes(spot=90, strike=100, rate=0.05, volatility=0.20, time_to_expiry=0)
        assert bs.call_price() == 0

    def test_implied_volatility(self):
        """Test implied volatility calculation."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.25, 0.5
        bs = BlackScholes(spot, strike, rate, vol, time)
        market_price = bs.call_price()

        # Calculate IV from market price
        iv = bs.implied_volatility(market_price, "call")
        assert abs(iv - vol) < 0.001


class TestBinomialTree:
    """Tests for Binomial Tree model."""

    def test_european_converges_to_bs(self):
        """Test that European binomial converges to Black-Scholes."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        bs = BlackScholes(spot, strike, rate, vol, time)
        binomial = BinomialTree(spot, strike, rate, vol, time, steps=200, american=False)

        bs_price = bs.call_price()
        bin_price = binomial.call_price()

        # Should be within 1% of BS price
        assert abs(bin_price - bs_price) / bs_price < 0.01

    def test_american_put_geq_european(self):
        """Test that American put >= European put."""
        spot, strike, rate, vol, time = 100, 110, 0.05, 0.20, 1.0

        euro = BinomialTree(spot, strike, rate, vol, time, steps=100, american=False)
        amer = BinomialTree(spot, strike, rate, vol, time, steps=100, american=True)

        assert amer.put_price() >= euro.put_price()

    def test_american_call_equals_european_no_dividend(self):
        """Test American call = European call with no dividends."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        euro = BinomialTree(spot, strike, rate, vol, time, steps=100, american=False)
        amer = BinomialTree(spot, strike, rate, vol, time, steps=100, american=True)

        # For non-dividend paying stock, American call = European call
        assert abs(amer.call_price() - euro.call_price()) < 0.01


class TestMonteCarlo:
    """Tests for Monte Carlo model."""

    def test_call_price_close_to_bs(self):
        """Test MC call price is close to Black-Scholes."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        bs = BlackScholes(spot, strike, rate, vol, time)
        mc = MonteCarlo(spot, strike, rate, vol, time, num_paths=50000, seed=42)

        bs_price = bs.call_price()
        mc_result = mc.price_with_stats("call")

        # MC should be within 2% of BS
        assert abs(mc_result.price - bs_price) / bs_price < 0.02

    def test_confidence_interval_contains_bs(self):
        """Test that BS price is within MC confidence interval."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        bs = BlackScholes(spot, strike, rate, vol, time)
        mc = MonteCarlo(spot, strike, rate, vol, time, num_paths=50000, seed=42)

        bs_price = bs.call_price()
        mc_result = mc.price_with_stats("call")

        # BS price should be within MC 95% CI
        assert mc_result.confidence_interval[0] <= bs_price <= mc_result.confidence_interval[1]

    def test_more_paths_reduces_error(self):
        """Test that more paths reduces standard error."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        mc_small = MonteCarlo(spot, strike, rate, vol, time, num_paths=1000, seed=42)
        mc_large = MonteCarlo(spot, strike, rate, vol, time, num_paths=50000, seed=42)

        result_small = mc_small.price_with_stats("call")
        result_large = mc_large.price_with_stats("call")

        assert result_large.std_error < result_small.std_error

    def test_asian_option(self):
        """Test Asian option pricing."""
        spot, strike, rate, vol, time = 100, 100, 0.05, 0.20, 1.0

        mc = MonteCarlo(spot, strike, rate, vol, time, num_paths=10000, seed=42)
        result = mc.price_asian("call")

        # Asian call should be cheaper than vanilla due to averaging
        vanilla = mc.price_with_stats("call")
        assert result.price < vanilla.price


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
