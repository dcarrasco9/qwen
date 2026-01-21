#!/usr/bin/env python3
"""
Carney-China Trade Deal Options Analysis

Analyzes options for companies affected by the Canada-China trade deal:
- NTR (Nutrien) - Canola/fertilizer beneficiary
- BYDDY (BYD) - Chinese EV winner
- F (Ford) - US auto loser
- MGA (Magna International) - Auto parts, mixed exposure

Uses Black-Scholes pricing to find mispriced options.
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from tabulate import tabulate

from qwen.data import YahooDataProvider
from qwen.pricing import BlackScholes
from qwen.screener import MispricingScanner

# Symbols to analyze
SYMBOLS = {
    "NTR": {"name": "Nutrien", "thesis": "LONG - Canola farmer demand surge", "sector": "Agriculture"},
    "BYDDY": {"name": "BYD Company", "thesis": "LONG - Canadian EV market entry", "sector": "Chinese EV"},
    "F": {"name": "Ford Motor", "thesis": "SHORT - Canadian market erosion", "sector": "US Auto"},
    "MGA": {"name": "Magna International", "thesis": "MIXED - China pivot vs Ontario decline", "sector": "Auto Parts"},
}


def calculate_realized_vol(history: pd.DataFrame, window: int = 20) -> float:
    """Calculate annualized realized volatility from historical prices."""
    returns = history['Close'].pct_change().dropna()
    return returns.tail(window).std() * np.sqrt(252)


def analyze_options_chain(provider: YahooDataProvider, symbol: str, info: dict) -> dict:
    """Analyze options chain for a single symbol."""
    print(f"\n{'='*60}")
    print(f"  {symbol} - {info['name']}")
    print(f"  Thesis: {info['thesis']}")
    print(f"{'='*60}")

    result = {
        "symbol": symbol,
        "name": info["name"],
        "thesis": info["thesis"],
        "sector": info["sector"],
        "quote": None,
        "realized_vol": None,
        "expirations": [],
        "options_summary": [],
        "mispricing_opportunities": [],
        "recommended_trades": [],
    }

    try:
        # Get current quote
        quote = provider.get_quote(symbol)
        result["quote"] = {
            "last": quote.last,
            "bid": quote.bid,
            "ask": quote.ask,
        }
        print(f"\n  Current Price: ${quote.last:.2f}")

        # Get historical data for realized vol
        end = datetime.now()
        start = end - timedelta(days=90)
        history = provider.get_historical(symbol, start, end)

        if history.empty:
            print(f"  WARNING: No historical data available for {symbol}")
            return result

        realized_vol = calculate_realized_vol(history)
        result["realized_vol"] = realized_vol
        print(f"  Realized Vol (20d): {realized_vol*100:.1f}%")

        # Get risk-free rate
        rate = provider.get_risk_free_rate()
        print(f"  Risk-Free Rate: {rate*100:.2f}%")

        # Get available expirations
        expirations = provider.get_expirations(symbol)
        if not expirations:
            print(f"  WARNING: No options available for {symbol}")
            return result

        result["expirations"] = [exp.strftime("%Y-%m-%d") for exp in expirations[:5]]
        print(f"  Available Expirations: {len(expirations)} (showing first 5)")
        for exp in expirations[:5]:
            print(f"    - {exp.strftime('%Y-%m-%d')}")

        # Analyze first 2 expirations for detail
        for exp in expirations[:2]:
            chain = provider.get_options_chain(symbol, exp)
            if not chain:
                continue

            days_to_exp = (exp - datetime.now()).days
            if days_to_exp <= 0:
                continue

            time_to_exp = days_to_exp / 365

            print(f"\n  --- Expiration: {exp.strftime('%Y-%m-%d')} ({days_to_exp} days) ---")

            # Separate calls and puts
            calls = [c for c in chain if c.option_type == 'call']
            puts = [p for p in chain if p.option_type == 'put']

            # Find ATM options
            atm_strike = min(chain, key=lambda x: abs(x.strike - quote.last)).strike

            # Analyze ATM and near-money options
            analysis_rows = []
            for opt in chain:
                # Focus on ATM and slightly OTM options
                moneyness = opt.strike / quote.last
                if not (0.85 <= moneyness <= 1.15):
                    continue

                # Skip low volume/no IV
                if opt.volume < 10 or not opt.implied_volatility:
                    continue

                # Calculate theoretical price with realized vol
                bs_realized = BlackScholes(
                    spot=quote.last,
                    strike=opt.strike,
                    rate=rate,
                    volatility=realized_vol,
                    time_to_expiry=time_to_exp
                )

                bs_market = BlackScholes(
                    spot=quote.last,
                    strike=opt.strike,
                    rate=rate,
                    volatility=opt.implied_volatility,
                    time_to_expiry=time_to_exp
                )

                if opt.option_type == 'call':
                    theo_price = bs_realized.call_price()
                    greeks = bs_realized.greeks('call')
                else:
                    theo_price = bs_realized.put_price()
                    greeks = bs_realized.greeks('put')

                market_mid = opt.mid if opt.mid else opt.last
                if not market_mid or market_mid <= 0:
                    continue

                edge = theo_price - market_mid
                edge_pct = (edge / market_mid) * 100
                iv_vs_rv = (opt.implied_volatility / realized_vol - 1) * 100

                analysis_rows.append({
                    "Type": opt.option_type.upper()[0],
                    "Strike": f"${opt.strike:.0f}",
                    "Bid": f"${opt.bid:.2f}" if opt.bid else "-",
                    "Ask": f"${opt.ask:.2f}" if opt.ask else "-",
                    "Mid": f"${market_mid:.2f}",
                    "Theo": f"${theo_price:.2f}",
                    "Edge": f"${edge:+.2f}",
                    "Edge%": f"{edge_pct:+.1f}%",
                    "IV": f"{opt.implied_volatility*100:.0f}%",
                    "IV/RV": f"{iv_vs_rv:+.0f}%",
                    "Delta": f"{greeks.delta:.2f}",
                    "Vol": opt.volume,
                    "OI": opt.open_interest,
                })

                # Flag significant mispricing
                if abs(edge_pct) > 10:
                    result["mispricing_opportunities"].append({
                        "expiration": exp.strftime("%Y-%m-%d"),
                        "type": opt.option_type,
                        "strike": opt.strike,
                        "market_mid": market_mid,
                        "theo_price": theo_price,
                        "edge": edge,
                        "edge_pct": edge_pct,
                        "iv": opt.implied_volatility,
                        "realized_vol": realized_vol,
                        "volume": opt.volume,
                        "delta": greeks.delta,
                    })

            if analysis_rows:
                result["options_summary"].append({
                    "expiration": exp.strftime("%Y-%m-%d"),
                    "days": days_to_exp,
                    "options": analysis_rows,
                })

                # Print summary table
                print(tabulate(analysis_rows, headers="keys", tablefmt="simple"))

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

    return result


def generate_trade_recommendations(results: list[dict]) -> list[dict]:
    """Generate trade recommendations based on analysis."""
    recommendations = []

    for r in results:
        symbol = r["symbol"]
        thesis = r["thesis"]

        if not r["mispricing_opportunities"]:
            continue

        # Sort by edge percentage
        opps = sorted(r["mispricing_opportunities"], key=lambda x: abs(x["edge_pct"]), reverse=True)

        for opp in opps[:3]:  # Top 3 per symbol
            # Determine trade direction based on thesis and mispricing
            is_long_thesis = "LONG" in thesis
            is_underpriced = opp["edge_pct"] > 0

            if is_long_thesis and opp["type"] == "call" and is_underpriced:
                action = "BUY"
                rationale = "Bullish thesis + underpriced call"
            elif is_long_thesis and opp["type"] == "put" and not is_underpriced:
                action = "SELL"
                rationale = "Bullish thesis + overpriced put (cash-secured)"
            elif not is_long_thesis and opp["type"] == "put" and is_underpriced:
                action = "BUY"
                rationale = "Bearish thesis + underpriced put"
            elif not is_long_thesis and opp["type"] == "call" and not is_underpriced:
                action = "SELL"
                rationale = "Bearish thesis + overpriced call (covered)"
            elif "MIXED" in thesis:
                # For mixed, trade the mispricing direction
                if is_underpriced:
                    action = "BUY"
                    rationale = "Neutral thesis + underpriced option"
                else:
                    action = "SELL"
                    rationale = "Neutral thesis + overpriced option"
            else:
                continue

            recommendations.append({
                "Symbol": symbol,
                "Action": action,
                "Type": opp["type"].upper(),
                "Strike": f"${opp['strike']:.0f}",
                "Exp": opp["expiration"],
                "Market": f"${opp['market_mid']:.2f}",
                "Theo": f"${opp['theo_price']:.2f}",
                "Edge%": f"{opp['edge_pct']:+.1f}%",
                "Delta": f"{opp['delta']:.2f}",
                "Rationale": rationale,
            })

    return recommendations


def run_mispricing_scanner(provider: YahooDataProvider, symbols: list[str]) -> pd.DataFrame:
    """Run the built-in mispricing scanner."""
    print("\n" + "="*60)
    print("  MISPRICING SCANNER RESULTS")
    print("="*60)

    rate = provider.get_risk_free_rate()
    scanner = MispricingScanner(
        data_provider=provider,
        risk_free_rate=rate,
        min_edge_pct=5.0,
        min_volume=50,
    )

    df = scanner.scan_watchlist(symbols)
    return df


def main():
    """Main analysis function."""
    print("\n" + "#"*60)
    print("#  CARNEY-CHINA TRADE DEAL OPTIONS ANALYSIS")
    print("#  Date:", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("#"*60)

    provider = YahooDataProvider()

    # Analyze each symbol
    results = []
    for symbol, info in SYMBOLS.items():
        result = analyze_options_chain(provider, symbol, info)
        results.append(result)

    # Generate recommendations
    print("\n" + "="*60)
    print("  TRADE RECOMMENDATIONS")
    print("="*60)

    recommendations = generate_trade_recommendations(results)
    if recommendations:
        print("\n" + tabulate(recommendations, headers="keys", tablefmt="grid"))
    else:
        print("\n  No clear trade recommendations based on current pricing.")

    # Run mispricing scanner
    scanner_results = run_mispricing_scanner(provider, list(SYMBOLS.keys()))
    if not scanner_results.empty:
        print("\n  Scanner found", len(scanner_results), "opportunities:")
        print(tabulate(scanner_results.head(10), headers="keys", tablefmt="simple", showindex=False))

    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)

    for r in results:
        print(f"\n  {r['symbol']} ({r['name']}):")
        if r['quote']:
            print(f"    Price: ${r['quote']['last']:.2f}")
        if r['realized_vol']:
            print(f"    Realized Vol: {r['realized_vol']*100:.1f}%")
        print(f"    Mispricing Opportunities: {len(r['mispricing_opportunities'])}")

    print("\n" + "#"*60)
    print("#  Analysis Complete")
    print("#"*60 + "\n")

    return results, recommendations


if __name__ == "__main__":
    results, recommendations = main()
