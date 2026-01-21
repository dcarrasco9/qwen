"""Check current option positions on Alpaca."""
from alpaca.trading.client import TradingClient
from qwen.config import config

client = TradingClient(
    api_key=config.alpaca_api_key,
    secret_key=config.alpaca_secret_key,
    paper=True
)

# Get account info
account = client.get_account()
print(f"Account Status: {account.status}")
print(f"Cash: ${float(account.cash):,.2f}")
print(f"Buying Power: ${float(account.buying_power):,.2f}")
print(f"Options Buying Power: ${float(account.options_buying_power):,.2f}")

# Get positions
positions = client.get_all_positions()
print(f"\nPositions: {len(positions)}")
for pos in positions:
    qty = float(pos.qty)
    cost = float(pos.cost_basis)
    current = float(pos.current_price) if pos.current_price else 0
    pnl = float(pos.unrealized_pl) if pos.unrealized_pl else 0
    print(f"  {pos.symbol}: {qty:+.0f} @ ${cost/abs(qty)/100:.2f} | Current: ${current:.2f} | P&L: ${pnl:+,.2f}")

# Get open orders
orders = client.get_orders(status="open")
print(f"\nOpen Orders: {len(orders)}")
for order in orders:
    print(f"  {order.id}: {order.side} {order.qty}x {order.symbol} @ ${float(order.limit_price) if order.limit_price else 'MKT'} - {order.status}")
