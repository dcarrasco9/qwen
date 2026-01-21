#!/usr/bin/env python3
"""
Options Profit/Loss Scenario Analysis
Carney-China Trade Deal Plays
"""

from datetime import datetime, timedelta
import numpy as np
from tabulate import tabulate
from qwen.data import YahooDataProvider
from qwen.pricing import BlackScholes


def get_option_price(provider, symbol, strike, opt_type, target_days):
    """Get the best matching option price."""
    exps = provider.get_expirations(symbol)
    if not exps:
        return None, None, None

    # Find closest expiration to target
    best_exp = min(exps, key=lambda x: abs((x - datetime.now()).days - target_days))
    chain = provider.get_options_chain(symbol, best_exp)

    # Find the strike
    matches = [o for o in chain if o.option_type == opt_type and abs(o.strike - strike) < 0.5]
    if not matches:
        # Find closest strike
        opts = [o for o in chain if o.option_type == opt_type]
        if not opts:
            return None, None, None
        matches = [min(opts, key=lambda x: abs(x.strike - strike))]

    opt = matches[0]
    return opt, best_exp, (best_exp - datetime.now()).days


def calculate_scenarios(opt_type, action, strike, premium, spot):
    """Calculate profit/loss scenarios at expiration."""
    scenarios = []

    # Define price movement scenarios (percentage moves)
    moves = [-30, -20, -15, -10, -5, 0, 5, 10, 15, 20, 30]

    for move in moves:
        future_price = spot * (1 + move/100)

        # Calculate option intrinsic value at expiration
        if opt_type == 'call':
            intrinsic = max(0, future_price - strike)
        else:
            intrinsic = max(0, strike - future_price)

        # Calculate P&L per contract (100 shares)
        if action == 'buy':
            pnl = (intrinsic - premium) * 100
            pnl_pct = ((intrinsic - premium) / premium) * 100 if premium > 0 else 0
        else:  # sell
            pnl = (premium - intrinsic) * 100
            # For sold options, max profit is premium received
            pnl_pct = (pnl / (premium * 100)) * 100 if premium > 0 else 0

        scenarios.append({
            'move': move,
            'price': future_price,
            'intrinsic': intrinsic,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
        })

    return scenarios


def main():
    provider = YahooDataProvider()
    rate = provider.get_risk_free_rate()

    print('#' * 75)
    print('#  OPTIONS PROFIT/LOSS SCENARIOS')
    print('#  Carney-China Trade Deal Plays')
    print('#  Date:', datetime.now().strftime('%Y-%m-%d %H:%M'))
    print('#' * 75)

    # Define the trades we want to analyze
    TRADES = [
        {'symbol': 'NTR', 'type': 'call', 'action': 'buy', 'strike': 67, 'exp_days': 11, 'thesis': 'LONG - Canola demand surge'},
        {'symbol': 'NTR', 'type': 'put', 'action': 'sell', 'strike': 62, 'exp_days': 11, 'thesis': 'LONG - Cash secured put'},
        {'symbol': 'F', 'type': 'put', 'action': 'buy', 'strike': 14, 'exp_days': 11, 'thesis': 'SHORT - Canadian market erosion'},
        {'symbol': 'NIO', 'type': 'call', 'action': 'buy', 'strike': 5, 'exp_days': 30, 'thesis': 'LONG - China EV play'},
        {'symbol': 'XPEV', 'type': 'call', 'action': 'buy', 'strike': 21, 'exp_days': 30, 'thesis': 'LONG - Magna partnership'},
        {'symbol': 'MGA', 'type': 'put', 'action': 'sell', 'strike': 50, 'exp_days': 32, 'thesis': 'NEUTRAL - Sell IV premium'},
    ]

    all_trades = []

    for trade in TRADES:
        symbol = trade['symbol']

        try:
            # Get current price
            quote = provider.get_quote(symbol)
            spot = quote.last

            # Get option data
            opt, exp_date, days = get_option_price(
                provider, symbol, trade['strike'], trade['type'], trade['exp_days']
            )

            if not opt:
                print(f"Could not find {symbol} {trade['strike']} {trade['type']}")
                continue

            # Get premium (ask for buys, bid for sells)
            if trade['action'] == 'buy':
                premium = opt.ask if opt.ask else opt.last
            else:
                premium = opt.bid if opt.bid else opt.last

            if not premium or premium <= 0:
                print(f"No valid premium for {symbol}")
                continue

            # Calculate breakeven
            if trade['type'] == 'call':
                breakeven = opt.strike + premium
            else:
                breakeven = opt.strike - premium

            # Calculate scenarios
            scenarios = calculate_scenarios(
                trade['type'], trade['action'],
                opt.strike, premium, spot
            )

            # Find worst/best case
            worst_case = min(scenarios, key=lambda x: x['pnl'])
            best_case = max(scenarios, key=lambda x: x['pnl'])

            # For sold options, calculate max loss more accurately
            if trade['action'] == 'sell':
                if trade['type'] == 'put':
                    # Max loss on short put = (strike - 0) * 100 - premium received
                    max_loss = (opt.strike * 100) - (premium * 100)
                    worst_case = {'pnl': -max_loss, 'move': -100, 'price': 0}
                else:
                    # Max loss on short call = unlimited (use -50% as proxy)
                    pass

            # Store trade info
            all_trades.append({
                'symbol': symbol,
                'trade': f"{trade['action'].upper()} ${opt.strike:.0f} {trade['type'].upper()}",
                'exp': exp_date.strftime('%m/%d'),
                'spot': spot,
                'strike': opt.strike,
                'premium': premium,
                'breakeven': breakeven,
                'days': days,
                'worst_pnl': worst_case['pnl'],
                'worst_move': worst_case['move'],
                'best_pnl': best_case['pnl'],
                'best_move': best_case['move'],
                'scenarios': scenarios,
                'thesis': trade['thesis'],
                'action': trade['action'],
                'type': trade['type'],
                'iv': opt.implied_volatility if opt.implied_volatility else 0,
                'volume': opt.volume,
                'oi': opt.open_interest,
            })

        except Exception as e:
            print(f"Error with {symbol}: {e}")
            import traceback
            traceback.print_exc()

    # Print summary table
    print('\n' + '=' * 75)
    print('  TRADE SUMMARY (per 1 contract = 100 shares)')
    print('=' * 75)

    summary = []
    for t in all_trades:
        action_word = "Pay" if t['action'] == 'buy' else "Receive"
        summary.append({
            'Symbol': t['symbol'],
            'Trade': t['trade'],
            'Exp': t['exp'],
            'Stock': f"${t['spot']:.2f}",
            'Premium': f"{action_word} ${t['premium']:.2f}",
            'Cost/Credit': f"${t['premium']*100:,.0f}",
            'Breakeven': f"${t['breakeven']:.2f}",
            'Max Loss': f"${t['worst_pnl']:,.0f}",
            'Max Gain': f"${t['best_pnl']:+,.0f}",
        })

    print(tabulate(summary, headers='keys', tablefmt='grid'))

    # Detailed scenarios for each trade
    for t in all_trades:
        print('\n' + '=' * 75)
        print(f"  {t['symbol']}: {t['trade']}")
        print(f"  Expiration: {t['exp']} ({t['days']} days)")
        print(f"  Thesis: {t['thesis']}")
        print('=' * 75)

        action_word = "PAID" if t['action'] == 'buy' else "RECEIVED"
        print(f"\n  Current Stock Price:  ${t['spot']:.2f}")
        print(f"  Strike Price:         ${t['strike']:.0f}")
        print(f"  Premium {action_word}:     ${t['premium']:.2f}/share (${t['premium']*100:.0f}/contract)")
        print(f"  Implied Volatility:   {t['iv']*100:.0f}%")
        print(f"  Breakeven Price:      ${t['breakeven']:.2f}")
        print(f"  Volume: {t['volume']:,} | Open Interest: {t['oi']:,}")

        print(f"\n  SCENARIO ANALYSIS AT EXPIRATION:")
        print(f"  {'-'*68}")
        print(f"  {'Stock Move':>12} {'Stock Price':>12} {'Option Value':>14} {'P&L':>14} {'Return':>10}")
        print(f"  {'-'*68}")

        for s in t['scenarios']:
            # Highlight key levels
            marker = ''
            if abs(s['move']) < 0.5:
                marker = ' <- TODAY'

            # Determine if profitable
            if s['pnl'] > 0:
                pnl_str = f"+${s['pnl']:,.0f}"
            else:
                pnl_str = f"-${abs(s['pnl']):,.0f}"

            ret_str = f"{s['pnl_pct']:+.0f}%" if abs(s['pnl_pct']) < 1000 else ("MAX" if s['pnl_pct'] > 0 else "LOSS")

            print(f"  {s['move']:>+10}%  ${s['price']:>10.2f}   ${s['intrinsic']:>12.2f}   {pnl_str:>12}   {ret_str:>8}{marker}")

        print(f"  {'-'*68}")

        # Summary
        print(f"\n  WORST CASE (Stock {t['worst_move']:+}%):  ${t['worst_pnl']:,.0f}")
        print(f"  BEST CASE (Stock {t['best_move']:+}%):   ${t['best_pnl']:+,.0f}")

        # Risk/Reward ratio
        if t['worst_pnl'] < 0 and t['best_pnl'] > 0:
            rr = abs(t['best_pnl'] / t['worst_pnl'])
            print(f"  RISK/REWARD RATIO:    1:{rr:.1f}")

        # Breakeven move required
        be_move = ((t['breakeven'] / t['spot']) - 1) * 100
        print(f"  BREAKEVEN MOVE:       {be_move:+.1f}%")

    # Portfolio summary
    print('\n' + '#' * 75)
    print('#  PORTFOLIO SUMMARY (All 6 Trades Combined)')
    print('#' * 75)

    total_debit = sum(t['premium'] * 100 for t in all_trades if t['action'] == 'buy')
    total_credit = sum(t['premium'] * 100 for t in all_trades if t['action'] == 'sell')
    net_cost = total_debit - total_credit

    # Calculate combined worst/best
    total_worst = sum(t['worst_pnl'] for t in all_trades)
    total_best = sum(t['best_pnl'] for t in all_trades)

    print(f"""
  CAPITAL REQUIRED:
  -----------------
  Premium Paid (Long Options):     ${total_debit:>10,.0f}
  Premium Received (Short Options): ${total_credit:>10,.0f}
  Net Debit:                        ${net_cost:>10,.0f}

  Cash Secured Put Collateral:
    - NTR $62 Put: $6,200 (if assigned)
    - MGA $50 Put: $5,000 (if assigned)
    Total Collateral Needed:        ${6200 + 5000:>10,}

  PROFIT/LOSS SCENARIOS:
  ----------------------
  Combined Worst Case:              ${total_worst:>+10,.0f}
  Combined Best Case:               ${total_best:>+10,.0f}

  INDIVIDUAL TRADE BREAKDOWN:
""")

    for t in all_trades:
        direction = "LONG" if t['action'] == 'buy' else "SHORT"
        print(f"    {t['symbol']:5} {t['trade']:20} Worst: ${t['worst_pnl']:>+8,.0f}  Best: ${t['best_pnl']:>+8,.0f}")

    print('\n' + '#' * 75)
    print('#  Analysis Complete')
    print('#' * 75)


if __name__ == "__main__":
    main()
