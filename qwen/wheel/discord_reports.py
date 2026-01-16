"""
Enhanced Discord Reporting for Wheel Automation

Provides:
- Daily morning briefings
- Position summaries with charts
- Weekly performance reports
- Price alerts
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from qwen.wheel.state import WheelStateManager, WheelState
from qwen.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)


@dataclass
class PriceAlert:
    """Price alert configuration."""
    symbol: str
    target_price: float
    direction: str  # 'above' or 'below'
    triggered: bool = False
    created_at: str = ""


class DiscordReporter:
    """
    Enhanced Discord reporting with rich embeds and scheduled reports.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        self.data_provider = YahooDataProvider()
        self.state_manager = WheelStateManager()
        self.price_alerts: list[PriceAlert] = []

    def _send_webhook(self, payload: dict) -> bool:
        """Send payload to Discord webhook."""
        if not self.webhook_url:
            logger.warning("Discord webhook not configured")
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                self.webhook_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Qwen-Wheel-Automation/1.0",
                },
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 204
        except URLError as e:
            logger.error(f"Discord webhook error: {e}")
            return False

    def send_morning_briefing(self) -> bool:
        """
        Send morning briefing with market overview and position status.
        """
        positions = self.state_manager.get_all_positions()
        active = [p for p in positions.values() if p.state != WheelState.IDLE]

        # Build position summary
        position_lines = []
        total_premium = 0

        for pos in positions.values():
            total_premium += pos.total_premium_collected

            if pos.state == WheelState.IDLE:
                status = "⚪ Idle"
            elif pos.state == WheelState.PUT_OPEN:
                opt = pos.active_option
                status = f"🟡 Put ${opt.strike:.0f} ({opt.days_to_expiration}d)"
            elif pos.state == WheelState.HOLDING_SHARES:
                status = f"🔵 Holding {pos.shares_owned} shares"
            elif pos.state == WheelState.CALL_OPEN:
                opt = pos.active_option
                status = f"🟢 Call ${opt.strike:.0f} ({opt.days_to_expiration}d)"
            else:
                status = pos.state.value

            position_lines.append(f"**{pos.symbol}**: {status}")

        # Get current prices for active positions
        price_lines = []
        for pos in positions.values():
            try:
                quote = self.data_provider.get_quote(pos.symbol)
                price_lines.append(f"{pos.symbol}: ${quote.last:.2f}")
            except:
                pass

        embed = {
            "title": "🌅 Morning Briefing",
            "description": f"**{datetime.now().strftime('%A, %B %d, %Y')}**",
            "color": 0x3498DB,
            "fields": [
                {
                    "name": "📊 Positions",
                    "value": "\n".join(position_lines) if position_lines else "No positions",
                    "inline": False,
                },
                {
                    "name": "💰 Total Premium",
                    "value": f"${total_premium:.2f}",
                    "inline": True,
                },
                {
                    "name": "🎯 Active",
                    "value": str(len(active)),
                    "inline": True,
                },
            ],
            "footer": {"text": "Qwen Wheel Automation"},
            "timestamp": datetime.now().isoformat(),
        }

        if price_lines:
            embed["fields"].append({
                "name": "📈 Current Prices",
                "value": " | ".join(price_lines),
                "inline": False,
            })

        return self._send_webhook({"embeds": [embed]})

    def send_daily_summary(self) -> bool:
        """
        Send end-of-day summary with P&L and activity.
        """
        positions = self.state_manager.get_all_positions()
        summary = self.state_manager.get_summary()

        # Calculate today's activity
        today = datetime.now().date().isoformat()
        todays_trades = []
        for pos in positions.values():
            for trade in pos.trades:
                if trade.timestamp.startswith(today):
                    todays_trades.append(trade)

        trade_summary = f"{len(todays_trades)} trades today" if todays_trades else "No trades today"

        embed = {
            "title": "📊 Daily Summary",
            "description": f"Market Close - {datetime.now().strftime('%B %d, %Y')}",
            "color": 0x2ECC71 if summary['total_premium_collected'] > 0 else 0x95A5A6,
            "fields": [
                {
                    "name": "💵 Total Premium Collected",
                    "value": f"${summary['total_premium_collected']:.2f}",
                    "inline": True,
                },
                {
                    "name": "🔄 Cycles Completed",
                    "value": str(summary['total_cycles_completed']),
                    "inline": True,
                },
                {
                    "name": "📈 Active Positions",
                    "value": str(summary['active_positions']),
                    "inline": True,
                },
                {
                    "name": "📝 Activity",
                    "value": trade_summary,
                    "inline": False,
                },
            ],
            "footer": {"text": "Qwen Wheel Automation"},
            "timestamp": datetime.now().isoformat(),
        }

        return self._send_webhook({"embeds": [embed]})

    def send_weekly_report(self) -> bool:
        """
        Send weekly performance report.
        """
        positions = self.state_manager.get_all_positions()

        # Calculate weekly stats
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        weekly_trades = []
        weekly_premium = 0.0

        for pos in positions.values():
            for trade in pos.trades:
                if trade.timestamp >= week_ago:
                    weekly_trades.append(trade)
                    if trade.premium:
                        weekly_premium += trade.premium

        # Position breakdown
        by_state = {}
        for pos in positions.values():
            state = pos.state.value
            by_state[state] = by_state.get(state, 0) + 1

        state_summary = " | ".join([f"{k}: {v}" for k, v in by_state.items()])

        embed = {
            "title": "📈 Weekly Performance Report",
            "description": f"Week ending {datetime.now().strftime('%B %d, %Y')}",
            "color": 0x9B59B6,
            "fields": [
                {
                    "name": "💰 Weekly Premium",
                    "value": f"${weekly_premium:.2f}",
                    "inline": True,
                },
                {
                    "name": "📊 Trades This Week",
                    "value": str(len(weekly_trades)),
                    "inline": True,
                },
                {
                    "name": "📍 Position States",
                    "value": state_summary or "None",
                    "inline": False,
                },
            ],
            "footer": {"text": "Qwen Wheel Automation"},
            "timestamp": datetime.now().isoformat(),
        }

        # Add top performers
        if positions:
            top = sorted(
                positions.values(),
                key=lambda p: p.total_premium_collected,
                reverse=True
            )[:3]

            top_lines = [f"{p.symbol}: ${p.total_premium_collected:.2f}" for p in top]
            embed["fields"].append({
                "name": "🏆 Top Performers",
                "value": "\n".join(top_lines),
                "inline": False,
            })

        return self._send_webhook({"embeds": [embed]})

    def add_price_alert(
        self,
        symbol: str,
        target_price: float,
        direction: str = "below",
    ) -> None:
        """
        Add a price alert.

        Args:
            symbol: Stock ticker
            target_price: Price to trigger alert
            direction: 'above' or 'below'
        """
        alert = PriceAlert(
            symbol=symbol.upper(),
            target_price=target_price,
            direction=direction,
            created_at=datetime.now().isoformat(),
        )
        self.price_alerts.append(alert)
        logger.info(f"Added price alert: {symbol} {direction} ${target_price}")

    def check_price_alerts(self) -> list[PriceAlert]:
        """
        Check all price alerts and send notifications for triggered ones.

        Returns:
            List of triggered alerts
        """
        triggered = []

        for alert in self.price_alerts:
            if alert.triggered:
                continue

            try:
                quote = self.data_provider.get_quote(alert.symbol)
                current_price = quote.last

                should_trigger = (
                    (alert.direction == "above" and current_price >= alert.target_price) or
                    (alert.direction == "below" and current_price <= alert.target_price)
                )

                if should_trigger:
                    alert.triggered = True
                    triggered.append(alert)

                    # Send Discord alert
                    self._send_price_alert(alert, current_price)

            except Exception as e:
                logger.error(f"Error checking alert for {alert.symbol}: {e}")

        return triggered

    def _send_price_alert(self, alert: PriceAlert, current_price: float) -> bool:
        """Send a price alert notification."""
        direction_emoji = "📈" if alert.direction == "above" else "📉"
        color = 0x2ECC71 if alert.direction == "above" else 0xE74C3C

        embed = {
            "title": f"{direction_emoji} Price Alert: {alert.symbol}",
            "description": f"**{alert.symbol}** is now {alert.direction} ${alert.target_price:.2f}",
            "color": color,
            "fields": [
                {
                    "name": "Current Price",
                    "value": f"${current_price:.2f}",
                    "inline": True,
                },
                {
                    "name": "Target",
                    "value": f"${alert.target_price:.2f}",
                    "inline": True,
                },
                {
                    "name": "Direction",
                    "value": alert.direction.upper(),
                    "inline": True,
                },
            ],
            "footer": {"text": "Qwen Price Alert"},
            "timestamp": datetime.now().isoformat(),
        }

        return self._send_webhook({"embeds": [embed]})

    def send_position_update(self, symbol: str) -> bool:
        """
        Send detailed position update for a symbol.
        """
        pos = self.state_manager.get_position(symbol)

        try:
            quote = self.data_provider.get_quote(symbol)
            current_price = quote.last
        except:
            current_price = None

        # Determine color based on state
        color_map = {
            WheelState.IDLE: 0x95A5A6,
            WheelState.PUT_OPEN: 0xF1C40F,
            WheelState.HOLDING_SHARES: 0x3498DB,
            WheelState.CALL_OPEN: 0x2ECC71,
        }

        fields = [
            {
                "name": "State",
                "value": pos.state.value,
                "inline": True,
            },
            {
                "name": "Premium Collected",
                "value": f"${pos.total_premium_collected:.2f}",
                "inline": True,
            },
            {
                "name": "Cycles",
                "value": str(pos.cycle_count),
                "inline": True,
            },
        ]

        if current_price:
            fields.append({
                "name": "Current Price",
                "value": f"${current_price:.2f}",
                "inline": True,
            })

        if pos.active_option:
            opt = pos.active_option
            fields.append({
                "name": f"Active {opt.option_type.upper()}",
                "value": f"${opt.strike:.2f} strike, {opt.days_to_expiration} DTE",
                "inline": False,
            })

        if pos.shares_owned > 0:
            fields.append({
                "name": "Shares",
                "value": f"{pos.shares_owned} @ ${pos.cost_basis:.2f}",
                "inline": True,
            })

            if current_price:
                unrealized = (current_price - pos.cost_basis) * pos.shares_owned
                fields.append({
                    "name": "Unrealized P&L",
                    "value": f"${unrealized:+.2f}",
                    "inline": True,
                })

        embed = {
            "title": f"📋 Position: {symbol}",
            "color": color_map.get(pos.state, 0x95A5A6),
            "fields": fields,
            "footer": {"text": "Qwen Wheel Automation"},
            "timestamp": datetime.now().isoformat(),
        }

        return self._send_webhook({"embeds": [embed]})

    def send_analysis(self, symbol: str) -> bool:
        """
        Send wheel opportunity analysis to Discord.
        """
        from qwen.wheel.strike_selector import StrikeSelector

        selector = StrikeSelector()

        try:
            analysis = selector.analyze_wheel_opportunity(symbol.upper())
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return False

        fields = [
            {
                "name": "Current Price",
                "value": f"${analysis['current_price']:.2f}",
                "inline": True,
            },
        ]

        if analysis.get("put_opportunity"):
            put = analysis["put_opportunity"]
            fields.append({
                "name": "🔴 Put Opportunity",
                "value": (
                    f"Strike: ${put['strike']:.2f}\n"
                    f"Premium: ${put['premium']:.2f}\n"
                    f"Delta: {put['delta']:.3f}\n"
                    f"DTE: {put['dte']}\n"
                    f"**ROI: {put['annualized_roi']:.1%}**"
                ),
                "inline": True,
            })

        if analysis.get("call_opportunity"):
            call = analysis["call_opportunity"]
            fields.append({
                "name": "🟢 Call Opportunity",
                "value": (
                    f"Strike: ${call['strike']:.2f}\n"
                    f"Premium: ${call['premium']:.2f}\n"
                    f"Delta: {call['delta']:.3f}\n"
                    f"DTE: {call['dte']}\n"
                    f"**ROI: {call['annualized_roi']:.1%}**"
                ),
                "inline": True,
            })

        if analysis.get("estimated_wheel_return"):
            fields.append({
                "name": "📊 Est. Wheel Return",
                "value": f"**{analysis['estimated_wheel_return']:.1%}** annualized",
                "inline": False,
            })

        embed = {
            "title": f"🎡 Wheel Analysis: {symbol.upper()}",
            "color": 0x3498DB,
            "fields": fields,
            "footer": {"text": "Qwen Wheel Automation"},
            "timestamp": datetime.now().isoformat(),
        }

        return self._send_webhook({"embeds": [embed]})


# Convenience functions
def send_morning_briefing():
    """Send morning briefing to Discord."""
    reporter = DiscordReporter()
    return reporter.send_morning_briefing()


def send_daily_summary():
    """Send daily summary to Discord."""
    reporter = DiscordReporter()
    return reporter.send_daily_summary()


def send_weekly_report():
    """Send weekly report to Discord."""
    reporter = DiscordReporter()
    return reporter.send_weekly_report()


def send_analysis(symbol: str):
    """Send analysis to Discord."""
    reporter = DiscordReporter()
    return reporter.send_analysis(symbol)
