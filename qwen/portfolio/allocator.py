"""
Income-Based Portfolio Allocation

Allocates investment capital based on income, risk tolerance,
and market opportunities. Designed for systematic wealth building.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal
import numpy as np


@dataclass
class IncomeProfile:
    """User's income and financial profile."""

    annual_salary: float
    tax_bracket: float = 0.32  # Marginal tax rate
    state_tax: float = 0.05
    retirement_contribution_pct: float = 0.10  # 401k contribution
    emergency_months: int = 6  # Months of expenses in emergency fund
    monthly_expenses: float = 4000
    existing_investments: float = 0
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"

    @property
    def effective_tax_rate(self) -> float:
        """Estimate effective total tax rate."""
        # Simplified: federal + state + FICA
        return self.tax_bracket + self.state_tax + 0.0765

    @property
    def annual_take_home(self) -> float:
        """Estimated annual take-home after taxes and 401k."""
        gross = self.annual_salary
        retirement = gross * self.retirement_contribution_pct
        taxable = gross - retirement
        taxes = taxable * self.effective_tax_rate
        return taxable - taxes

    @property
    def monthly_take_home(self) -> float:
        """Monthly take-home pay."""
        return self.annual_take_home / 12

    @property
    def monthly_investable(self) -> float:
        """Monthly amount available for investing."""
        return self.monthly_take_home - self.monthly_expenses

    @property
    def emergency_fund_target(self) -> float:
        """Target emergency fund amount."""
        return self.monthly_expenses * self.emergency_months


@dataclass
class PortfolioAllocation:
    """Recommended portfolio allocation."""

    # Monthly allocations
    monthly_investment: float
    core_etf_allocation: float  # Long-term index funds
    options_allocation: float  # Active options strategies
    cash_reserve: float  # Dry powder for opportunities

    # Strategy breakdown
    strategies: dict = field(default_factory=dict)

    # Risk metrics
    max_single_position_pct: float = 0.10
    max_options_pct: float = 0.30
    target_annual_return: float = 0.15

    def summary(self) -> str:
        """Print allocation summary."""
        return f"""
Portfolio Allocation Summary
============================
Monthly Investment: ${self.monthly_investment:,.0f}

Allocation:
  Core ETFs:      ${self.core_etf_allocation:,.0f} ({self.core_etf_allocation/self.monthly_investment*100:.0f}%)
  Options:        ${self.options_allocation:,.0f} ({self.options_allocation/self.monthly_investment*100:.0f}%)
  Cash Reserve:   ${self.cash_reserve:,.0f} ({self.cash_reserve/self.monthly_investment*100:.0f}%)

Risk Limits:
  Max Single Position: {self.max_single_position_pct*100:.0f}%
  Max Options:         {self.max_options_pct*100:.0f}%
  Target Return:       {self.target_annual_return*100:.0f}%
"""


class IncomeBasedAllocator:
    """
    Allocates investment capital based on income profile.

    Philosophy:
    1. Build emergency fund first
    2. Max tax-advantaged accounts (401k, IRA)
    3. Core holdings in low-cost index funds
    4. Satellite positions in options strategies
    5. Keep dry powder for opportunities
    """

    def __init__(self, profile: IncomeProfile):
        self.profile = profile

    def calculate_allocation(self) -> PortfolioAllocation:
        """
        Calculate recommended portfolio allocation.

        Returns:
            PortfolioAllocation with breakdown
        """
        monthly = self.profile.monthly_investable

        # Base allocations by risk tolerance
        if self.profile.risk_tolerance == "conservative":
            core_pct = 0.80
            options_pct = 0.10
            cash_pct = 0.10
            max_options = 0.15
        elif self.profile.risk_tolerance == "moderate":
            core_pct = 0.60
            options_pct = 0.25
            cash_pct = 0.15
            max_options = 0.30
        else:  # aggressive
            core_pct = 0.40
            options_pct = 0.40
            cash_pct = 0.20
            max_options = 0.50

        allocation = PortfolioAllocation(
            monthly_investment=monthly,
            core_etf_allocation=monthly * core_pct,
            options_allocation=monthly * options_pct,
            cash_reserve=monthly * cash_pct,
            max_options_pct=max_options,
        )

        # Add strategy breakdown
        allocation.strategies = self._get_strategy_breakdown(allocation)

        return allocation

    def _get_strategy_breakdown(self, allocation: PortfolioAllocation) -> dict:
        """Break down options allocation into strategies."""

        options_budget = allocation.options_allocation

        if self.profile.risk_tolerance == "conservative":
            return {
                "covered_calls": options_budget * 0.50,
                "cash_secured_puts": options_budget * 0.40,
                "protective_puts": options_budget * 0.10,
            }
        elif self.profile.risk_tolerance == "moderate":
            return {
                "covered_calls": options_budget * 0.30,
                "cash_secured_puts": options_budget * 0.30,
                "iron_condors": options_budget * 0.20,
                "directional": options_budget * 0.15,
                "event_driven": options_budget * 0.05,
            }
        else:  # aggressive
            return {
                "directional_calls": options_budget * 0.30,
                "directional_puts": options_budget * 0.20,
                "straddles": options_budget * 0.15,
                "iron_condors": options_budget * 0.15,
                "event_driven": options_budget * 0.10,
                "leaps": options_budget * 0.10,
            }

    def get_monthly_plan(self, current_month: int = None) -> dict:
        """
        Get specific monthly investment plan.

        Args:
            current_month: Month number (1-12)

        Returns:
            Dict with specific actions for the month
        """
        if current_month is None:
            current_month = datetime.now().month

        allocation = self.calculate_allocation()
        monthly = allocation.monthly_investment

        plan = {
            "month": current_month,
            "total_to_invest": monthly,
            "actions": [],
        }

        # Core ETF buys
        plan["actions"].append({
            "type": "core_buy",
            "amount": allocation.core_etf_allocation,
            "description": "Buy VTI/VOO/QQQ (dollar-cost average)",
            "timing": "First week of month",
        })

        # Options strategies
        if allocation.options_allocation > 0:
            for strategy, amount in allocation.strategies.items():
                if amount > 50:  # Minimum threshold
                    plan["actions"].append({
                        "type": "options",
                        "strategy": strategy,
                        "amount": amount,
                        "description": self._get_strategy_description(strategy),
                        "timing": "When opportunity identified",
                    })

        # Cash reserve
        plan["actions"].append({
            "type": "cash_reserve",
            "amount": allocation.cash_reserve,
            "description": "Hold for dips/opportunities",
            "timing": "Deploy on 5%+ market drops",
        })

        return plan

    def _get_strategy_description(self, strategy: str) -> str:
        """Get description for each strategy."""
        descriptions = {
            "covered_calls": "Sell calls on existing positions for income",
            "cash_secured_puts": "Sell puts on stocks you want to own",
            "iron_condors": "Sell premium on range-bound stocks",
            "directional": "Buy calls/puts on high-conviction plays",
            "directional_calls": "Long calls on bullish setups",
            "directional_puts": "Long puts on bearish setups",
            "straddles": "Buy straddles before expected moves",
            "event_driven": "Play earnings, geopolitical events",
            "protective_puts": "Hedge existing positions",
            "leaps": "Long-dated calls for leveraged exposure",
        }
        return descriptions.get(strategy, strategy)

    def project_growth(
        self,
        years: int = 10,
        annual_return: float = None,
    ) -> dict:
        """
        Project portfolio growth over time.

        Args:
            years: Number of years to project
            annual_return: Expected annual return (default based on allocation)

        Returns:
            Dict with year-by-year projections
        """
        allocation = self.calculate_allocation()

        if annual_return is None:
            annual_return = allocation.target_annual_return

        monthly_contribution = allocation.monthly_investment
        starting_value = self.profile.existing_investments

        projections = []
        current_value = starting_value

        for year in range(1, years + 1):
            # Add monthly contributions with monthly compounding
            for month in range(12):
                current_value += monthly_contribution
                current_value *= (1 + annual_return / 12)

            total_contributed = starting_value + (monthly_contribution * 12 * year)
            gains = current_value - total_contributed

            projections.append({
                "year": year,
                "portfolio_value": current_value,
                "total_contributed": total_contributed,
                "total_gains": gains,
                "gain_pct": gains / total_contributed * 100 if total_contributed > 0 else 0,
            })

        return {
            "starting_value": starting_value,
            "monthly_contribution": monthly_contribution,
            "annual_return": annual_return,
            "projections": projections,
            "final_value": projections[-1]["portfolio_value"],
        }


def create_profile_128k() -> IncomeProfile:
    """
    Create income profile for $128k salary.

    Assumes:
    - NYC/high-cost area (higher taxes, expenses)
    - 32% federal marginal rate
    - 10% 401k contribution
    - Moderate risk tolerance
    """
    return IncomeProfile(
        annual_salary=128000,
        tax_bracket=0.32,
        state_tax=0.06,  # NY/CA state tax
        retirement_contribution_pct=0.10,
        emergency_months=6,
        monthly_expenses=4500,  # Higher for NYC/SF
        existing_investments=0,
        risk_tolerance="moderate",
    )
