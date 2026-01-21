"""Debug yfinance options data directly."""
import yfinance as yf

for symbol in ['LUNR', 'ONDS']:
    print(f"\n{'='*60}")
    print(f"=== {symbol} ===")

    ticker = yf.Ticker(symbol)
    exps = ticker.options
    print(f"Expirations: {exps[:5]}")

    if exps:
        # Get Feb 2026 expiration (around 30 DTE)
        target_exp = '2026-02-20'
        if target_exp in exps:
            chain = ticker.option_chain(target_exp)
            puts = chain.puts

            print(f"\nPuts columns: {puts.columns.tolist()}")
            print(f"\nPuts for {target_exp}:")
            print(puts[['strike', 'bid', 'ask', 'lastPrice', 'openInterest', 'impliedVolatility']].to_string())
