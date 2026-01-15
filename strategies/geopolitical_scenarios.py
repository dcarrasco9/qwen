"""
Geopolitical Scenario-Based Trading Strategies
US-Iran / Venezuela Crisis - January 2026

These strategies are designed to capitalize on specific geopolitical
outcomes. Choose the scenario that best matches your market view.
"""

from dataclasses import dataclass
from typing import Literal
from qwen.pricing import BlackScholes


@dataclass
class ScenarioTrade:
    """Represents a single trade within a scenario."""
    symbol: str
    name: str
    direction: Literal["long_call", "long_put"]
    current_price: float
    strike: float
    days_to_expiry: int
    volatility: float
    rationale: str

    @property
    def premium(self) -> float:
        """Calculate option premium using Black-Scholes."""
        bs = BlackScholes(
            self.current_price,
            self.strike,
            0.05,  # Risk-free rate
            self.volatility,
            self.days_to_expiry / 365
        )
        if "call" in self.direction:
            return bs.call_price()
        return bs.put_price()

    @property
    def contract_cost(self) -> float:
        """Cost per contract (100 shares)."""
        return self.premium * 100

    def contracts_for_allocation(self, allocation: float) -> int:
        """Number of contracts for given dollar allocation."""
        return int(allocation / self.contract_cost)


@dataclass
class GeopoliticalScenario:
    """A complete scenario-based trading plan."""
    name: str
    thesis: str
    probability: str
    timeframe: str
    triggers: list[str]
    trades: list[ScenarioTrade]

    def print_plan(self, total_allocation: float = 20000):
        """Print the complete trading plan."""
        print("=" * 70)
        print(f"SCENARIO: {self.name}")
        print("=" * 70)
        print(f"\nTHESIS: {self.thesis}")
        print(f"\nPROBABILITY: {self.probability}")
        print(f"TIMEFRAME: {self.timeframe}")
        print(f"\nTRIGGERS TO WATCH:")
        for trigger in self.triggers:
            print(f"  - {trigger}")

        print("\n" + "-" * 70)
        print("TRADES:")
        print("-" * 70)

        allocation_per_trade = total_allocation / len(self.trades)

        for i, trade in enumerate(self.trades, 1):
            contracts = trade.contracts_for_allocation(allocation_per_trade)
            print(f"\n{i}. {trade.symbol} ({trade.name}) - {trade.direction.upper()}")
            print(f"   Current:  ${trade.current_price:.2f}")
            print(f"   Strike:   ${trade.strike}")
            print(f"   Expiry:   {trade.days_to_expiry} days")
            print(f"   Premium:  ${trade.premium:.2f}/share (${trade.contract_cost:.0f}/contract)")
            print(f"   Contracts: {contracts} (${contracts * trade.contract_cost:,.0f})")
            print(f"   Rationale: {trade.rationale}")


# =============================================================================
# SCENARIO 1: IRAN ESCALATION
# =============================================================================

IRAN_ESCALATION = GeopoliticalScenario(
    name="IRAN ESCALATION - US Military Strikes",
    thesis="""US strikes Iranian nuclear sites, Iran threatens Strait of Hormuz.
Oil spikes $10-20/barrel, defense stocks surge, airlines collapse, gold rallies.""",
    probability="60-70%",
    timeframe="1-4 weeks",
    triggers=[
        "US announces military action on Iran",
        "Iran closes or threatens Strait of Hormuz",
        "Oil breaks above $65/barrel",
        "Major Iranian military response to protests",
    ],
    trades=[
        ScenarioTrade(
            symbol="OXY",
            name="Occidental Petroleum",
            direction="long_call",
            current_price=44.32,
            strike=50,
            days_to_expiry=30,
            volatility=0.40,
            rationale="Leveraged oil play. $10 oil spike = 25-35% move in OXY."
        ),
        ScenarioTrade(
            symbol="LMT",
            name="Lockheed Martin",
            direction="long_call",
            current_price=572.70,
            strike=600,
            days_to_expiry=30,
            volatility=0.25,
            rationale="Defense contractor. Iran war = massive defense spending."
        ),
        ScenarioTrade(
            symbol="UAL",
            name="United Airlines",
            direction="long_put",
            current_price=110.75,
            strike=100,
            days_to_expiry=30,
            volatility=0.45,
            rationale="Airlines crushed by oil spikes. Fuel is 20-30% of costs."
        ),
        ScenarioTrade(
            symbol="GLD",
            name="Gold ETF",
            direction="long_call",
            current_price=425.94,
            strike=440,
            days_to_expiry=30,
            volatility=0.15,
            rationale="Safe haven. War + uncertainty = gold higher."
        ),
    ]
)


# =============================================================================
# SCENARIO 2: IRAN REGIME COLLAPSE / DE-ESCALATION
# =============================================================================

IRAN_DEESCALATION = GeopoliticalScenario(
    name="IRAN REGIME COLLAPSE - De-escalation",
    thesis="""Iranian regime collapses under protest pressure. New government
seeks Western relations. Oil drops as war premium fades, risk-on rally.""",
    probability="25-35%",
    timeframe="2-8 weeks",
    triggers=[
        "Supreme Leader Khamenei death/removal",
        "Military/IRGC defections to protesters",
        "Oil falls below $58 (war premium unwinding)",
        "Trump announces diplomatic solution",
    ],
    trades=[
        ScenarioTrade(
            symbol="USO",
            name="Oil ETF",
            direction="long_put",
            current_price=72.61,
            strike=68,
            days_to_expiry=45,
            volatility=0.35,
            rationale="War premium unwinds. USO drops 10-15% to $62-65."
        ),
        ScenarioTrade(
            symbol="DAL",
            name="Delta Airlines",
            direction="long_call",
            current_price=68.49,
            strike=75,
            days_to_expiry=45,
            volatility=0.40,
            rationale="Airlines recover when oil drops. Was $75+ before crisis."
        ),
        ScenarioTrade(
            symbol="LMT",
            name="Lockheed Martin",
            direction="long_put",
            current_price=572.70,
            strike=540,
            days_to_expiry=45,
            volatility=0.25,
            rationale="Defense gives back gains. 'Buy rumor, sell news' play."
        ),
        ScenarioTrade(
            symbol="QQQ",
            name="Nasdaq-100 ETF",
            direction="long_call",
            current_price=619.55,
            strike=640,
            days_to_expiry=45,
            volatility=0.18,
            rationale="Risk-on rally when geopolitical risk fades."
        ),
    ]
)


# =============================================================================
# HEDGE STRATEGY: USO STRADDLE
# =============================================================================

def uso_straddle_hedge():
    """
    If uncertain which scenario plays out, use a straddle on USO
    to profit from volatility in either direction.
    """
    uso_price = 72.61
    strike = 72
    days = 30
    vol = 0.35

    bs = BlackScholes(uso_price, strike, 0.05, vol, days/365)
    call_premium = bs.call_price()
    put_premium = bs.put_price()
    total_cost = (call_premium + put_premium) * 100

    breakeven_up = strike + call_premium + put_premium
    breakeven_down = strike - call_premium - put_premium

    return {
        "strategy": "USO Straddle",
        "strike": strike,
        "expiry_days": days,
        "call_premium": call_premium,
        "put_premium": put_premium,
        "total_cost": total_cost,
        "breakeven_up": breakeven_up,
        "breakeven_down": breakeven_down,
        "rationale": "Profit from big move in either direction. "
                     "Iran escalation = oil up, de-escalation = oil down."
    }


def run_scenario_analysis():
    """Print both scenarios for comparison."""
    print("\n" + "=" * 70)
    print("GEOPOLITICAL SCENARIO ANALYSIS")
    print("US-Iran / Venezuela Crisis - January 2026")
    print("=" * 70)

    print("""
CURRENT SITUATION:
- Venezuela: Maduro captured Jan 3, power vacuum, 800k bbl/day at risk
- Iran: Mass protests (2,400+ killed), 81% chance of US strikes
- Oil: WTI at $61 (up $4 in 4 days), Strait of Hormuz concerns
- Defense stocks: Already rallying 6-10% in 5 days
- Polymarket: 81% odds of US strike on Iran by end of January
    """)

    IRAN_ESCALATION.print_plan(20000)
    print("\n")
    IRAN_DEESCALATION.print_plan(15000)

    print("\n" + "=" * 70)
    print("HEDGE: USO STRADDLE")
    print("=" * 70)
    hedge = uso_straddle_hedge()
    print(f"""
If uncertain, use straddle to profit from volatility either way:

USO ${hedge['strike']} Straddle (30 days)
- Call Premium: ${hedge['call_premium']:.2f}
- Put Premium:  ${hedge['put_premium']:.2f}
- Total Cost:   ${hedge['total_cost']:.0f} per straddle
- Breakeven:    ${hedge['breakeven_down']:.2f} - ${hedge['breakeven_up']:.2f}
    """)


if __name__ == "__main__":
    run_scenario_analysis()
