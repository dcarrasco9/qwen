"""
Market Open Trade Executor

Executes scheduled wheel trades at market open with Discord notifications.
Can be run via Windows Task Scheduler or cron.

Usage:
    python scripts/market_open_trade.py --symbol LUNR --contracts 5
    python scripts/market_open_trade.py --symbol LUNR --contracts 5 --dry-run
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from qwen.broker.alpaca_options import AlpacaOptionsBroker
from qwen.data.yahoo import YahooDataProvider
from qwen.wheel.strike_selector import StrikeSelector
from qwen.wheel.notifications import (
    NotificationHub,
    DiscordNotifier,
    ConsoleNotifier,
    Notification,
    NotificationLevel,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "market_open_trade.log"),
    ]
)
logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def build_occ_symbol(underlying: str, expiration: datetime, strike: float, option_type: str) -> str:
    """Build OCC option symbol like LUNR260227P00018000."""
    exp_str = expiration.strftime("%y%m%d")
    opt_char = "P" if option_type.lower() == "put" else "C"
    strike_int = int(strike * 1000)
    return f"{underlying}{exp_str}{opt_char}{strike_int:08d}"


def execute_market_open_trade(
    symbol: str,
    contracts: int = 1,
    dry_run: bool = False,
    target_delta: float = 0.25,
    min_dte: int = 25,
    max_dte: int = 45,
    min_premium: float = 0.50,
) -> dict:
    """
    Execute a cash-secured put trade at market open.

    Returns dict with trade details for Discord notification.
    """
    logger.info(f"Starting market open trade for {symbol}")
    logger.info(f"Contracts: {contracts}, Dry run: {dry_run}")

    # Initialize components
    data_provider = YahooDataProvider()
    strike_selector = StrikeSelector(data_provider=data_provider)

    # Find best put strike
    logger.info(f"Finding optimal put strike (delta={target_delta}, DTE={min_dte}-{max_dte})")
    put_candidate = strike_selector.find_put_strike(
        symbol=symbol,
        target_delta=target_delta,
        min_dte=min_dte,
        max_dte=max_dte,
        min_premium=min_premium,
    )

    if not put_candidate:
        raise ValueError(f"No suitable put found for {symbol}")

    contract = put_candidate.contract
    current_price = data_provider.get_quote(symbol).last

    # Build OCC symbol
    occ_symbol = build_occ_symbol(
        underlying=symbol,
        expiration=contract.expiration,
        strike=contract.strike,
        option_type="put",
    )

    # Calculate trade details
    premium_per_contract = contract.mid * 100
    total_premium = premium_per_contract * contracts
    collateral_per_contract = contract.strike * 100
    total_collateral = collateral_per_contract * contracts
    effective_cost_basis = contract.strike - contract.mid
    annualized_roi = put_candidate.annualized_return

    trade_details = {
        "symbol": symbol,
        "occ_symbol": occ_symbol,
        "action": "SELL PUT",
        "strike": contract.strike,
        "premium": contract.mid,
        "expiration": contract.expiration.strftime("%Y-%m-%d"),
        "dte": put_candidate.days_to_expiration,
        "delta": put_candidate.delta,
        "contracts": contracts,
        "total_premium": total_premium,
        "total_collateral": total_collateral,
        "effective_cost_basis": effective_cost_basis,
        "current_price": current_price,
        "annualized_roi": annualized_roi,
        "dry_run": dry_run,
        "timestamp": datetime.now(ET).isoformat(),
        "order_id": None,
        "status": "pending",
    }

    logger.info(f"Trade details: {trade_details}")

    if dry_run:
        logger.info("DRY RUN - No order placed")
        trade_details["status"] = "dry_run"
        trade_details["order_id"] = "DRY-RUN-123"
    else:
        # Place the order
        logger.info(f"Placing order: SELL {contracts}x {occ_symbol} @ ${contract.mid:.2f}")

        options_broker = AlpacaOptionsBroker()
        order = options_broker.sell_option(
            symbol=occ_symbol,
            qty=contracts,
            order_type="limit",
            limit_price=contract.mid,
        )

        trade_details["order_id"] = order.id
        trade_details["status"] = str(order.status)
        logger.info(f"Order placed: {order.id} - Status: {order.status}")

    return trade_details


def send_discord_notification(trade_details: dict, is_error: bool = False, error_msg: str = None):
    """Send trade notification to Discord."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set, skipping notification")
        return

    notifier = DiscordNotifier(webhook_url=webhook_url)

    if is_error:
        # Error notification
        notification = Notification(
            title="Trade Execution Failed",
            message=error_msg or "Unknown error",
            level=NotificationLevel.ERROR,
            data={"Symbol": trade_details.get("symbol", "Unknown")},
        )
    else:
        # Success notification
        is_dry_run = trade_details.get("dry_run", False)
        title = f"{'[DRY RUN] ' if is_dry_run else ''}Wheel Trade Executed"

        fields = {
            "Symbol": trade_details["symbol"],
            "Action": trade_details["action"],
            "Strike": f"${trade_details['strike']:.2f}",
            "Premium": f"${trade_details['premium']:.2f}/share",
            "Expiration": f"{trade_details['expiration']} ({trade_details['dte']} DTE)",
            "Delta": f"{trade_details['delta']:.3f}",
            "Contracts": str(trade_details["contracts"]),
            "Total Premium": f"${trade_details['total_premium']:.2f}",
            "Collateral": f"${trade_details['total_collateral']:,.2f}",
            "Cost Basis": f"${trade_details['effective_cost_basis']:.2f}",
            "Ann. ROI": f"{trade_details['annualized_roi']:.1%}",
            "Order ID": trade_details.get("order_id", "N/A"),
            "Status": trade_details.get("status", "unknown"),
        }

        notification = Notification(
            title=title,
            message=f"SELL {trade_details['contracts']}x {trade_details['occ_symbol']} @ ${trade_details['premium']:.2f}",
            level=NotificationLevel.INFO,
            data=fields,
        )

    success = notifier.send(notification)
    if success:
        logger.info("Discord notification sent")
    else:
        logger.warning("Failed to send Discord notification")


def main():
    parser = argparse.ArgumentParser(description="Execute wheel trade at market open")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g., LUNR)")
    parser.add_argument("--contracts", type=int, default=1, help="Number of contracts")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without placing order")
    parser.add_argument("--delta", type=float, default=0.25, help="Target delta (default: 0.25)")
    parser.add_argument("--min-dte", type=int, default=25, help="Minimum DTE (default: 25)")
    parser.add_argument("--max-dte", type=int, default=45, help="Maximum DTE (default: 45)")
    parser.add_argument("--min-premium", type=float, default=0.50, help="Minimum premium (default: 0.50)")

    args = parser.parse_args()

    # Create logs directory if needed
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("MARKET OPEN TRADE EXECUTOR")
    logger.info(f"Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 60)

    try:
        trade_details = execute_market_open_trade(
            symbol=args.symbol,
            contracts=args.contracts,
            dry_run=args.dry_run,
            target_delta=args.delta,
            min_dte=args.min_dte,
            max_dte=args.max_dte,
            min_premium=args.min_premium,
        )

        send_discord_notification(trade_details)

        logger.info("Trade execution complete")
        print(f"\n{'='*60}")
        print(f"TRADE {'SIMULATED' if args.dry_run else 'EXECUTED'}")
        print(f"{'='*60}")
        print(f"Symbol: {trade_details['symbol']}")
        print(f"Action: {trade_details['action']}")
        print(f"Strike: ${trade_details['strike']:.2f}")
        print(f"Premium: ${trade_details['premium']:.2f} x {trade_details['contracts']} = ${trade_details['total_premium']:.2f}")
        print(f"Expiration: {trade_details['expiration']} ({trade_details['dte']} DTE)")
        print(f"Collateral: ${trade_details['total_collateral']:,.2f}")
        print(f"Annualized ROI: {trade_details['annualized_roi']:.1%}")
        print(f"Order ID: {trade_details.get('order_id', 'N/A')}")
        print(f"Status: {trade_details.get('status', 'unknown')}")

    except Exception as e:
        logger.error(f"Trade execution failed: {e}", exc_info=True)

        # Send error notification to Discord
        send_discord_notification(
            trade_details={"symbol": args.symbol},
            is_error=True,
            error_msg=str(e),
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
