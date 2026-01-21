"""Check Alpaca paper account balance."""
from qwen.broker.alpaca_options import AlpacaOptionsBroker

broker = AlpacaOptionsBroker()
acct = broker.get_account()

print(f"Cash: ${float(acct.cash):,.2f}")
print(f"Buying Power: ${float(acct.buying_power):,.2f}")

# Check for positions
positions = broker.get_positions()
print(f"\nPositions: {len(positions)}")
for pos in positions:
    print(f"  {pos.symbol}: {pos.quantity} @ ${pos.average_cost:.2f}")
