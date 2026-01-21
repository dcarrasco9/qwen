#!/usr/bin/env python3
"""
Live Market Scan for Carney-China Play
Uses Alpaca API for real-time quotes
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from tabulate import tabulate

from qwen.config import config
from qwen.data import YahooDataProvider

# Try to import Alpaca, fall back to Yahoo if not available
try:
    from qwen.data import AlpacaDataProvider
    HAS_ALPACA = config.has_alpaca_credentials
except ImportError:
    HAS_ALPACA = False

# Timezone setup
MARKET_TZ = ZoneInfo("America/New_York")
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def get_market_time():
    """Get current time in market timezone (Eastern)."""
    return datetime.now(MARKET_TZ)


def get_local_time():
    """Get current time in local timezone (Pacific)."""
    return datetime.now(LOCAL_TZ)


def is_market_open():
    """Check if US market is currently open."""
    now = get_market_time()
    # Market hours: 9:30 AM - 4:00 PM Eastern, Mon-Fri
    if now.weekday() >= 5:  # Weekend
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


# Our original trades from January 18
TRADES = [
    {
        'symbol': 'NTR',
        'trade': 'BUY $67 CALL',
        'entry_stock': 66.38,
        'entry_premium': 1.80,
        'strike': 67,
        'type': 'call',
        'action': 'buy',
        'exp_target': '01/30',
        'thesis': 'LONG - Canola demand'
    },
    {
        'symbol': 'F',
        'trade': 'BUY $14 PUT',
        'entry_stock': 13.60,
        'entry_premium': 0.52,
        'strike': 14,
        'type': 'put',
        'action': 'buy',
        'exp_target': '01/30',
        'thesis': 'SHORT - Canadian erosion'
    },
    {
        'symbol': 'NIO',
        'trade': 'BUY $5 CALL',
        'entry_stock': 4.71,
        'entry_premium': 0.22,
        'strike': 5,
        'type': 'call',
        'action': 'buy',
        'exp_target': '02/20',
        'thesis': 'LONG - China EV'
    },
    {
        'symbol': 'XPEV',
        'trade': 'BUY $21 CALL',
        'entry_stock': 20.65,
        'entry_premium': 1.39,
        'strike': 21,
        'type': 'call',
        'action': 'buy',
        'exp_target': '02/20',
        'thesis': 'LONG - Magna partnership'
    },
]


def main():
    market_time = get_market_time()
    local_time = get_local_time()
    market_status = "OPEN" if is_market_open() else "CLOSED"

    print('#' * 75)
    print('#  CARNEY-CHINA PLAY - LIVE MARKET SCAN')
    print('#' * 75)
    print(f'#  Market Time (ET): {market_time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'#  Local Time (PT):  {local_time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'#  Market Status:    {market_status}')
    print('#' * 75)

    # Initialize data provider
    if HAS_ALPACA:
        print('\n  Using: Alpaca API (real-time quotes)')
        provider = AlpacaDataProvider()
    else:
        print('\n  Using: Yahoo Finance (may be delayed)')
        print('  Note: Set ALPACA_API_KEY and ALPACA_SECRET_KEY for real-time data')
        provider = YahooDataProvider()

    results = []
    total_entry_cost = 0
    total_current_value = 0
    total_pnl = 0

    print('\n' + '=' * 75)
    print('  SCANNING POSITIONS...')
    print('=' * 75)

    for t in TRADES:
        try:
            symbol = t['symbol']
            print(f'\n  Scanning {symbol}...')

            # Get current stock quote
            quote = provider.get_quote(symbol)
            current_stock = quote.last

            stock_move = ((current_stock / t['entry_stock']) - 1) * 100

            # Get options chain
            exps = provider.get_expirations(symbol)
            if not exps:
                print(f'    No options expirations found for {symbol}')
                continue

            # Find matching expiration
            target_exp = None
            for exp in exps:
                if exp.strftime('%m/%d') == t['exp_target']:
                    target_exp = exp
                    break

            # If no exact match, find closest
            if not target_exp:
                target_exp = exps[0]

            days_left = (target_exp - datetime.now()).days

            # Get options chain for this expiration
            chain = provider.get_options_chain(symbol, target_exp)

            # Find our option
            opt = None
            for o in chain:
                if o.option_type == t['type'] and abs(o.strike - t['strike']) < 0.5:
                    opt = o
                    break

            if not opt:
                # Find closest strike
                matching = [o for o in chain if o.option_type == t['type']]
                if matching:
                    opt = min(matching, key=lambda x: abs(x.strike - t['strike']))

            if not opt:
                print(f'    Could not find {t["type"]} option near ${t["strike"]}')
                continue

            # Get current option price
            current_bid = opt.bid if opt.bid else 0
            current_ask = opt.ask if opt.ask else 0
            current_mid = (current_bid + current_ask) / 2 if current_bid and current_ask else opt.last or 0
            current_last = opt.last if opt.last else current_mid

            # Use bid for exit value (what we'd actually get)
            exit_price = current_bid if current_bid > 0 else current_last

            # Calculate P&L
            entry_cost = t['entry_premium'] * 100
            current_value = exit_price * 100
            pnl = current_value - entry_cost
            pnl_pct = (pnl / entry_cost) * 100 if entry_cost > 0 else 0

            total_entry_cost += entry_cost
            total_current_value += current_value
            total_pnl += pnl

            # Calculate intrinsic value
            if t['type'] == 'call':
                intrinsic = max(0, current_stock - opt.strike)
                moneyness = 'ITM' if current_stock > opt.strike else 'OTM'
            else:
                intrinsic = max(0, opt.strike - current_stock)
                moneyness = 'ITM' if current_stock < opt.strike else 'OTM'

            time_value = max(0, exit_price - intrinsic)

            # Check if thesis is correct
            if t['type'] == 'call':
                thesis_correct = stock_move > 0
            else:
                thesis_correct = stock_move < 0

            results.append({
                'symbol': symbol,
                'trade': t['trade'],
                'thesis': t['thesis'],
                'entry_stock': t['entry_stock'],
                'current_stock': current_stock,
                'stock_move': stock_move,
                'strike': opt.strike,
                'moneyness': moneyness,
                'entry_premium': t['entry_premium'],
                'current_bid': current_bid,
                'current_ask': current_ask,
                'current_last': current_last,
                'exit_price': exit_price,
                'intrinsic': intrinsic,
                'time_value': time_value,
                'iv': opt.implied_volatility if opt.implied_volatility else 0,
                'volume': opt.volume,
                'oi': opt.open_interest,
                'days_left': days_left,
                'exp': target_exp.strftime('%m/%d'),
                'entry_cost': entry_cost,
                'current_value': current_value,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'thesis_correct': thesis_correct,
            })

            # Print live data
            print(f'    Stock: ${current_stock:.2f} ({stock_move:+.2f}%)')
            print(f'    Option ${opt.strike} {t["type"].upper()}: Bid ${current_bid:.2f} / Ask ${current_ask:.2f}')
            print(f'    P&L: ${pnl:+.0f} ({pnl_pct:+.1f}%)')

        except Exception as e:
            print(f'    Error: {e}')
            import traceback
            traceback.print_exc()

    # Summary table
    print('\n' + '=' * 75)
    print('  POSITION SUMMARY')
    print('=' * 75)

    summary_table = []
    for r in results:
        status = 'WIN' if r['pnl'] > 0 else 'LOSS' if r['pnl'] < 0 else 'FLAT'
        thesis_status = 'RIGHT' if r['thesis_correct'] else 'WRONG'

        summary_table.append({
            'Symbol': r['symbol'],
            'Trade': r['trade'],
            'Stock': f"{r['stock_move']:+.1f}%",
            'Entry': f"${r['entry_premium']:.2f}",
            'Bid': f"${r['current_bid']:.2f}",
            'Ask': f"${r['current_ask']:.2f}",
            'Days': r['days_left'],
            'P&L': f"${r['pnl']:+,.0f}",
            'Return': f"{r['pnl_pct']:+.0f}%",
            'Status': status,
            'Thesis': thesis_status,
        })

    print(tabulate(summary_table, headers='keys', tablefmt='grid'))

    # Portfolio totals
    print('\n' + '=' * 75)
    print('  PORTFOLIO TOTALS')
    print('=' * 75)

    total_return = (total_pnl / total_entry_cost) * 100 if total_entry_cost > 0 else 0

    print(f'''
  Entry Date:         January 18, 2026
  Days in Trade:      {(datetime.now() - datetime(2026, 1, 18)).days} days

  Total Entry Cost:   ${total_entry_cost:,.0f}
  Current Value:      ${total_current_value:,.0f}

  TOTAL P&L:          ${total_pnl:+,.0f}
  TOTAL RETURN:       {total_return:+.1f}%
''')

    # Detailed analysis
    print('=' * 75)
    print('  DETAILED ANALYSIS')
    print('=' * 75)

    for r in results:
        print(f'''
  {r['symbol']}: {r['trade']}
  {'-' * 50}
  Thesis: {r['thesis']}
  Thesis Status: {'CORRECT - Stock moved as expected' if r['thesis_correct'] else 'WRONG - Stock moved opposite'}

  Stock:
    Entry:    ${r['entry_stock']:.2f}
    Current:  ${r['current_stock']:.2f}
    Move:     {r['stock_move']:+.2f}%

  Option (Exp: {r['exp']}, {r['days_left']} days left):
    Strike:   ${r['strike']:.2f} ({r['moneyness']})
    Entry:    ${r['entry_premium']:.2f}
    Bid/Ask:  ${r['current_bid']:.2f} / ${r['current_ask']:.2f}
    Last:     ${r['current_last']:.2f}
    IV:       {r['iv']*100:.0f}%
    Volume:   {r['volume']:,}
    OI:       {r['oi']:,}

  Value:
    Intrinsic: ${r['intrinsic']:.2f}
    Time Val:  ${r['time_value']:.2f}

  P&L:
    Entry:    ${r['entry_cost']:.0f}
    Current:  ${r['current_value']:.0f} (at bid)
    P&L:      ${r['pnl']:+,.0f} ({r['pnl_pct']:+.1f}%)
''')

    # Win/Loss summary
    wins = sum(1 for r in results if r['pnl'] > 0)
    losses = sum(1 for r in results if r['pnl'] < 0)
    thesis_right = sum(1 for r in results if r['thesis_correct'])

    print('=' * 75)
    print('  SCORECARD')
    print('=' * 75)
    print(f'''
  Trades: {len(results)}
  Wins:   {wins}
  Losses: {losses}

  Thesis Accuracy: {thesis_right}/{len(results)} ({thesis_right/len(results)*100:.0f}%)

  Best Trade:  {max(results, key=lambda x: x['pnl'])['symbol']} ({max(results, key=lambda x: x['pnl'])['trade']}) ${max(results, key=lambda x: x['pnl'])['pnl']:+,.0f}
  Worst Trade: {min(results, key=lambda x: x['pnl'])['symbol']} ({min(results, key=lambda x: x['pnl'])['trade']}) ${min(results, key=lambda x: x['pnl'])['pnl']:+,.0f}
''')

    print('#' * 75)
    print('#  Scan Complete')
    print('#' * 75)

    return results


if __name__ == "__main__":
    main()
