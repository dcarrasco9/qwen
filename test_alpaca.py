#!/usr/bin/env python3
"""
Test Alpaca Integration

Before running, set your environment variables:
    export ALPACA_API_KEY="PKAIVZJHIH5HBINJVCSKBZY2LC"
    export ALPACA_SECRET_KEY="EZcikaoaDTAwuCG7FiQPsn6e2evzGLNWNFEJVdksEmGc"
    export ALPACA_PAPER=true
"""

import os
import sys

def check_credentials():
    """Check if Alpaca credentials are set."""
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("=" * 60)
        print("ALPACA CREDENTIALS NOT SET")
        print("=" * 60)
        print("\nPlease set your Alpaca API credentials:")
        print()
        print('  export ALPACA_API_KEY="PKAIVZJHIH5HBINJVCSKBZY2LC"')
        print('  export ALPACA_SECRET_KEY="EZcikaoaDTAwuCG7FiQPsn6e2evzGLNWNFEJVdksEmGc"')
        print('  export ALPACA_PAPER=true')
        print()
        print("Get your keys from: https://app.alpaca.markets/")
        print("=" * 60)
        return False

    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"Paper Mode: {os.getenv('ALPACA_PAPER', 'true')}")
    return True


def test_broker():
    """Test the Alpaca broker connection."""
    print("\n" + "=" * 60)
    print("TESTING ALPACA BROKER")
    print("=" * 60)

    from qwen.broker import AlpacaBroker

    broker = AlpacaBroker(paper=True)

    # Get account info
    account = broker.get_account()
    print(f"\nAccount ID: {account.account_id}")
    print(f"  Equity:       ${account.equity:,.2f}")
    print(f"  Cash:         ${account.cash:,.2f}")
    print(f"  Buying Power: ${account.buying_power:,.2f}")
    print(f"  Day P&L:      ${account.day_pl:+,.2f}")
    print(f"  Paper Mode:   {account.is_paper}")

    # Check market status
    market_hours = broker.get_market_hours()
    print(f"\nMarket Status:")
    print(f"  Is Open: {market_hours['is_open']}")
    print(f"  Next Open: {market_hours['next_open']}")
    print(f"  Next Close: {market_hours['next_close']}")

    # Get positions
    positions = broker.get_positions()
    print(f"\nOpen Positions ({len(positions)}):")
    if positions:
        for pos in positions:
            print(f"  {pos.symbol:6} {pos.qty:>8.2f} @ ${pos.avg_entry_price:,.2f}  "
                  f"P&L: ${pos.unrealized_pl:+,.2f}")
    else:
        print("  No open positions")

    return broker


def test_paper_trade(broker):
    """Test a paper trade."""
    print("\n" + "=" * 60)
    print("TESTING PAPER TRADE")
    print("=" * 60)

    # Only trade if market is open or it's crypto
    market_hours = broker.get_market_hours()

    if market_hours['is_open']:
        print("\nMarket is OPEN - testing stock order...")
        symbol = "AAPL"
        qty = 1
    else:
        print("\nMarket is CLOSED - testing crypto order (24/7)...")
        symbol = "BTC/USD"
        qty = 0.001  # Small amount of BTC

    response = input(f"\nSubmit test order: BUY {qty} {symbol}? (y/n): ")

    if response.lower() == 'y':
        try:
            if "/" in symbol:
                order = broker.buy_crypto(symbol, qty)
            else:
                order = broker.market_buy(symbol, qty)

            print(f"\nOrder Submitted!")
            print(f"  Order ID: {order.id}")
            print(f"  Symbol:   {order.symbol}")
            print(f"  Side:     {order.side.value}")
            print(f"  Qty:      {order.qty}")
            print(f"  Status:   {order.status.value}")

            if order.filled_avg_price:
                print(f"  Filled @: ${order.filled_avg_price:,.2f}")

            return order
        except Exception as e:
            print(f"\nOrder failed: {e}")
            return None
    else:
        print("Order skipped.")
        return None


def test_live_runner(broker):
    """Test the live runner with a strategy."""
    print("\n" + "=" * 60)
    print("TESTING LIVE RUNNER")
    print("=" * 60)

    from qwen.live import LiveRunner
    from qwen.backtest.strategy import SimpleMovingAverageCrossover

    runner = LiveRunner(broker)

    # Print current status
    runner.print_status()

    # Test running a strategy
    response = input("\nRun SMA crossover strategy on AAPL? (y/n): ")

    if response.lower() == 'y':
        strategy = SimpleMovingAverageCrossover("AAPL", short_window=10, long_window=30)
        orders = runner.run_once(strategy, "AAPL")

        if orders:
            print(f"\nStrategy generated {len(orders)} order(s):")
            for order in orders:
                print(f"  {order.side.value.upper()} {order.qty} {order.symbol} - {order.status.value}")
        else:
            print("\nNo signals generated (strategy is waiting for crossover)")

    return runner


def main():
    print("\n" + "=" * 60)
    print("QWEN - ALPACA INTEGRATION TEST")
    print("=" * 60)

    # Check credentials
    if not check_credentials():
        sys.exit(1)

    try:
        # Test broker
        broker = test_broker()

        # Test paper trade
        test_paper_trade(broker)

        # Test live runner
        test_live_runner(broker)

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED!")
        print("=" * 60)
        print("\nYour Alpaca integration is working. You can now:")
        print("  1. Execute trades: broker.market_buy('AAPL', 10)")
        print("  2. Run strategies: runner.run_once(strategy, 'AAPL')")
        print("  3. Trade crypto 24/7: broker.buy_crypto('BTC/USD', 0.01)")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
