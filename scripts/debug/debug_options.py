"""Debug script to check options chain data."""
from qwen.data.yahoo import YahooDataProvider
from datetime import datetime

provider = YahooDataProvider()

for symbol in ['LUNR', 'ONDS']:
    print(f'\n{"="*50}')
    print(f'=== {symbol} ===')
    print(f'{"="*50}')

    try:
        quote = provider.get_quote(symbol)
        print(f'Current price: ${quote.last:.2f}')
    except Exception as e:
        print(f'Error getting quote: {e}')
        continue

    exps = provider.get_expirations(symbol)
    print(f'Available expirations: {len(exps)}')

    today = datetime.now().date()
    for exp in exps[:5]:
        exp_date = exp.date() if isinstance(exp, datetime) else exp
        dte = (exp_date - today).days
        print(f'  {exp_date} ({dte} DTE)')

    # Get chain for first valid expiration (25-45 DTE)
    valid_exps = [e for e in exps if 25 <= (e.date() - today).days <= 45]
    print(f'\nValid expirations (25-45 DTE): {len(valid_exps)}')

    if valid_exps:
        chain = provider.get_options_chain(symbol, valid_exps[0])
        puts = [c for c in chain if c.option_type == 'put']
        print(f'Puts for {valid_exps[0].date()}: {len(puts)}')

        # Show puts around current price
        print(f'\nPuts (all):')
        for p in sorted(puts, key=lambda x: x.strike):
            oi_ok = "Y" if p.open_interest >= 10 else "N"
            prem_ok = "Y" if p.mid >= 0.50 else "N"
            print(f'  ${p.strike:6.2f} | Bid: ${p.bid:.2f} | Ask: ${p.ask:.2f} | Mid: ${p.mid:.2f} | OI: {p.open_interest:5d} {oi_ok} | IV: {p.implied_volatility or 0:.1%} | Prem: {prem_ok}')
    else:
        print('No valid expirations found!')
