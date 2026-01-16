"""
Discord Bot for Wheel Strategy

Unified bot that handles:
- Slash commands for interactive queries
- Scheduled notifications (briefings, alerts, reports)
- Position monitoring and trade alerts
"""

import asyncio
import logging
import os
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from qwen.wheel.state import WheelStateManager, WheelState
from qwen.wheel.strike_selector import StrikeSelector
from qwen.wheel.config import load_config
from qwen.wheel.engine import WheelEngine, WheelConfig as EngineConfig, SymbolConfig as EngineSymbolConfig
from qwen.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)

# US Eastern timezone for market hours
ET = ZoneInfo("America/New_York")

# Market hours
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

# Notification channel ID
NOTIFICATION_CHANNEL_ID = 1461858868224196680


def is_market_open() -> bool:
    """Check if US stock market is currently open."""
    now = datetime.now(ET)
    if now.weekday() >= 5:  # Weekend
        return False
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


class WheelBot(commands.Bot):
    """Discord bot for wheel strategy with integrated scheduling."""

    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Qwen Wheel Strategy Bot",
        )

        # Core components
        self.state_manager = WheelStateManager()
        self.strike_selector = StrikeSelector()
        self.config = load_config()
        self.provider = YahooDataProvider()

        # Notification channel
        self.notification_channel: Optional[discord.TextChannel] = None

        # Initialize wheel engine
        engine_symbols = [
            EngineSymbolConfig(
                symbol=s.symbol,
                enabled=s.enabled,
                target_put_delta=s.target_put_delta,
                target_call_delta=s.target_call_delta,
                min_dte=s.min_dte,
                max_dte=s.max_dte,
                min_premium=s.min_premium,
                max_positions=s.max_positions,
            )
            for s in self.config.symbols
        ]

        engine_config = EngineConfig(
            symbols=engine_symbols,
            check_interval_minutes=self.config.check_interval_minutes,
            market_hours_only=self.config.market_hours_only,
            max_total_capital=self.config.max_total_capital,
            paper_mode=self.config.paper_mode,
            min_buying_power_reserve=self.config.safety.min_buying_power_reserve,
            max_loss_per_position=self.config.safety.max_loss_per_position,
            stop_loss_percent=self.config.safety.stop_loss_percent,
            roll_dte_threshold=self.config.safety.roll_dte_threshold,
        )

        # Create a simple notification adapter for the engine
        self.engine = WheelEngine(
            state_manager=self.state_manager,
            notifications=None,  # We'll handle notifications through Discord
            config=engine_config,
        )

    async def setup_hook(self):
        """Set up slash commands and scheduled tasks."""
        await self.add_cog(WheelCommands(self))
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Bot logged in as {self.user}")

        # Get notification channel
        self.notification_channel = self.get_channel(NOTIFICATION_CHANNEL_ID)
        if self.notification_channel:
            logger.info(f"Notification channel: #{self.notification_channel.name}")
        else:
            logger.warning(f"Could not find notification channel {NOTIFICATION_CHANNEL_ID}")

        # Start scheduled tasks
        if not self.position_check_task.is_running():
            self.position_check_task.start()
        if not self.morning_briefing_task.is_running():
            self.morning_briefing_task.start()
        if not self.daily_summary_task.is_running():
            self.daily_summary_task.start()
        if not self.weekly_report_task.is_running():
            self.weekly_report_task.start()
        if not self.iv_alerts_task.is_running():
            self.iv_alerts_task.start()

        # Send startup notification
        await self.send_notification(
            title="🚀 Wheel Bot Started",
            description=f"Monitoring {len([s for s in self.config.symbols if s.enabled])} symbols",
            color=discord.Color.green(),
            fields=[
                ("Mode", "PAPER" if self.config.paper_mode else "LIVE", True),
                ("Check Interval", f"{self.config.check_interval_minutes} min", True),
                ("Symbols", ", ".join(s.symbol for s in self.config.symbols if s.enabled), False),
            ]
        )

        print(f"Bot logged in as {self.user}")
        print(f"Notification channel: #{self.notification_channel.name if self.notification_channel else 'NOT FOUND'}")
        print("Scheduled tasks started")

    async def send_notification(
        self,
        title: str,
        description: str = None,
        color: discord.Color = discord.Color.blue(),
        fields: list = None,
    ):
        """Send a notification embed to the notification channel."""
        if not self.notification_channel:
            logger.warning("No notification channel set")
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(),
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        embed.set_footer(text="Qwen Wheel Automation")

        try:
            await self.notification_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def send_trade_alert(self, action: str, symbol: str, details: dict):
        """Send a trade alert notification."""
        emoji = {
            "sell_to_open": "📉",
            "buy_to_close": "📈",
            "assigned": "📋",
            "called_away": "📤",
            "expired": "⏰",
        }.get(action, "💰")

        color = {
            "sell_to_open": discord.Color.green(),
            "buy_to_close": discord.Color.orange(),
            "assigned": discord.Color.blue(),
            "called_away": discord.Color.purple(),
            "expired": discord.Color.gold(),
        }.get(action, discord.Color.grey())

        fields = []
        if details.get("strike"):
            fields.append(("Strike", f"${details['strike']:.2f}", True))
        if details.get("premium"):
            fields.append(("Premium", f"${details['premium']:.2f}", True))
        if details.get("expiration"):
            fields.append(("Expiration", details['expiration'], True))

        await self.send_notification(
            title=f"{emoji} {action.replace('_', ' ').title()}: {symbol}",
            color=color,
            fields=fields,
        )

    # ==================== SCHEDULED TASKS ====================

    @tasks.loop(minutes=60)
    async def position_check_task(self):
        """Check all positions hourly."""
        if self.config.market_hours_only and not is_market_open():
            logger.debug("Market closed, skipping position check")
            return

        logger.info("Running scheduled position check...")

        for sym_config in self.config.symbols:
            if sym_config.enabled:
                try:
                    # Check position (engine will execute trades if needed)
                    result = self.engine.check_and_execute(sym_config.symbol)

                    # If a trade was made, send alert
                    if result and result.get("action"):
                        await self.send_trade_alert(
                            action=result["action"],
                            symbol=sym_config.symbol,
                            details=result,
                        )
                except Exception as e:
                    logger.error(f"Error checking {sym_config.symbol}: {e}")
                    await self.send_notification(
                        title=f"⚠️ Error: {sym_config.symbol}",
                        description=str(e),
                        color=discord.Color.red(),
                    )

    @position_check_task.before_loop
    async def before_position_check(self):
        await self.wait_until_ready()

    @tasks.loop(time=time(9, 0, tzinfo=ET))
    async def morning_briefing_task(self):
        """Send morning briefing at 9:00 AM ET on weekdays."""
        now = datetime.now(ET)
        if now.weekday() >= 5:  # Skip weekends
            return

        await self._send_morning_briefing()

    @morning_briefing_task.before_loop
    async def before_morning_briefing(self):
        await self.wait_until_ready()

    @tasks.loop(time=time(16, 5, tzinfo=ET))
    async def daily_summary_task(self):
        """Send daily summary at 4:05 PM ET."""
        await self._send_daily_summary()

    @daily_summary_task.before_loop
    async def before_daily_summary(self):
        await self.wait_until_ready()

    @tasks.loop(time=time(18, 0, tzinfo=ET))
    async def weekly_report_task(self):
        """Send weekly report at 6:00 PM ET on Sundays."""
        now = datetime.now(ET)
        if now.weekday() != 6:  # Only on Sunday
            return

        await self._send_weekly_report()

    @weekly_report_task.before_loop
    async def before_weekly_report(self):
        await self.wait_until_ready()

    @tasks.loop(time=[time(9, 30, tzinfo=ET), time(13, 30, tzinfo=ET), time(15, 30, tzinfo=ET)])
    async def iv_alerts_task(self):
        """Check IV alerts at 9:30 AM, 1:30 PM, 3:30 PM ET on weekdays."""
        now = datetime.now(ET)
        if now.weekday() >= 5:  # Skip weekends
            return

        await self._check_iv_alerts()

    @iv_alerts_task.before_loop
    async def before_iv_alerts(self):
        await self.wait_until_ready()

    # ==================== NOTIFICATION METHODS ====================

    async def _send_morning_briefing(self):
        """Send morning briefing."""
        logger.info("Sending morning briefing...")

        positions = self.state_manager.get_all_positions()
        summary = self.state_manager.get_summary()

        active_text = ""
        opportunities_text = ""

        for sym_config in self.config.symbols:
            if not sym_config.enabled:
                continue

            symbol = sym_config.symbol
            pos = positions.get(symbol)

            try:
                quote = self.provider.get_quote(symbol)
                price = quote.last

                if pos and pos.state != WheelState.IDLE:
                    if pos.active_option:
                        opt = pos.active_option
                        active_text += f"**{symbol}**: ${price:.2f} | {opt.option_type.upper()} ${opt.strike:.2f} | {opt.days_to_expiration} DTE\n"
                else:
                    analysis = self.strike_selector.analyze_wheel_opportunity(symbol)
                    if analysis.get("put_opportunity"):
                        put = analysis["put_opportunity"]
                        opportunities_text += f"**{symbol}**: ${price:.2f} | Put ${put['strike']:.2f} @ ${put['premium']:.2f} ({put['annualized_roi']:.0%})\n"
            except Exception as e:
                logger.warning(f"Error getting data for {symbol}: {e}")

        fields = [
            ("Active Positions", active_text or "None", False),
            ("Opportunities", opportunities_text or "No new opportunities", False),
            ("Total Premium", f"${summary.get('total_premium_collected', 0):.2f}", True),
            ("Active", str(summary.get('active_positions', 0)), True),
        ]

        await self.send_notification(
            title="☀️ Morning Briefing",
            color=discord.Color.orange(),
            fields=fields,
        )

    async def _send_daily_summary(self):
        """Send daily summary."""
        logger.info("Sending daily summary...")

        summary = self.state_manager.get_summary()
        positions = self.state_manager.get_all_positions()

        position_text = ""
        for symbol, pos in positions.items():
            if pos.state != WheelState.IDLE:
                state_emoji = {
                    WheelState.PUT_OPEN: "🔴",
                    WheelState.HOLDING_SHARES: "🔵",
                    WheelState.CALL_OPEN: "🟢",
                }.get(pos.state, "⚪")
                position_text += f"{state_emoji} **{symbol}**: {pos.state.value}\n"

        fields = [
            ("Positions", position_text or "None active", False),
            ("Total Premium", f"${summary['total_premium_collected']:.2f}", True),
            ("Cycles", str(summary['total_cycles_completed']), True),
        ]

        await self.send_notification(
            title="📊 Daily Summary",
            color=discord.Color.blue(),
            fields=fields,
        )

    async def _send_weekly_report(self):
        """Send weekly P&L report."""
        logger.info("Sending weekly report...")

        positions = self.state_manager.get_all_positions()
        trades = self.state_manager.export_trades()

        total_premium = sum(p.total_premium_collected for p in positions.values())
        total_cycles = sum(p.cycle_count for p in positions.values())

        position_summary = ""
        for symbol, pos in positions.items():
            if pos.total_premium_collected > 0 or pos.state != WheelState.IDLE:
                position_summary += f"**{symbol}**: ${pos.total_premium_collected:.2f} collected, {pos.cycle_count} cycles\n"

        fields = [
            ("Performance", position_summary or "No active positions", False),
            ("Total Premium", f"${total_premium:.2f}", True),
            ("Cycles", str(total_cycles), True),
            ("Trades This Week", str(len(trades[-20:]) if trades else 0), True),
        ]

        await self.send_notification(
            title="📈 Weekly Wheel Report",
            color=discord.Color.gold(),
            fields=fields,
        )

    async def _check_iv_alerts(self):
        """Check for IV spike/crush alerts."""
        logger.debug("Checking IV levels...")

        try:
            from qwen.screener.volatility import VolatilityAnalyzer
            analyzer = VolatilityAnalyzer(self.provider)

            for sym_config in self.config.symbols:
                if not sym_config.enabled:
                    continue

                symbol = sym_config.symbol

                try:
                    regime = analyzer.analyze_symbol(symbol)

                    if regime.iv_percentile is not None:
                        if regime.iv_percentile >= 80:
                            await self.send_notification(
                                title=f"🔥 High IV Alert: {symbol}",
                                description=f"IV Rank {regime.iv_percentile:.0f}% - consider selling premium",
                                color=discord.Color.red(),
                                fields=[
                                    ("IV Percentile", f"{regime.iv_percentile:.0f}%", True),
                                    ("Regime", regime.vol_regime, True),
                                ],
                            )
                        elif regime.iv_percentile <= 20:
                            await self.send_notification(
                                title=f"❄️ Low IV Alert: {symbol}",
                                description=f"IV Rank {regime.iv_percentile:.0f}% - premium is cheap",
                                color=discord.Color.blue(),
                                fields=[
                                    ("IV Percentile", f"{regime.iv_percentile:.0f}%", True),
                                    ("Regime", regime.vol_regime, True),
                                ],
                            )
                except Exception as e:
                    logger.warning(f"Error analyzing IV for {symbol}: {e}")

        except ImportError:
            logger.debug("VolatilityAnalyzer not available")
        except Exception as e:
            logger.error(f"Error checking IV alerts: {e}")


class WheelCommands(commands.Cog):
    """Slash commands for wheel strategy."""

    def __init__(self, bot: WheelBot):
        self.bot = bot

    @app_commands.command(name="status", description="Show current wheel strategy status")
    async def status(self, interaction: discord.Interaction):
        """Show wheel status."""
        await interaction.response.defer()

        try:
            positions = self.bot.state_manager.get_all_positions()
            summary = self.bot.state_manager.get_summary()

            embed = discord.Embed(
                title="Wheel Strategy Status",
                color=discord.Color.gold(),
                timestamp=datetime.now(),
            )

            embed.add_field(
                name="Overview",
                value=f"**Active Positions:** {summary['active_positions']}\n"
                      f"**Total Premium:** ${summary['total_premium_collected']:.2f}\n"
                      f"**Cycles Completed:** {summary['total_cycles_completed']}",
                inline=False,
            )

            if positions:
                position_text = ""
                for symbol, pos in positions.items():
                    state_emoji = {
                        WheelState.IDLE: "⚪",
                        WheelState.PUT_OPEN: "🔴",
                        WheelState.HOLDING_SHARES: "🔵",
                        WheelState.CALL_OPEN: "🟢",
                    }.get(pos.state, "⚪")

                    position_text += f"{state_emoji} **{symbol}**: {pos.state.value}\n"

                    if pos.active_option:
                        opt = pos.active_option
                        position_text += f"   └ {opt.option_type.upper()} ${opt.strike:.2f} | {opt.days_to_expiration} DTE\n"

                embed.add_field(name="Positions", value=position_text or "None", inline=False)
            else:
                embed.add_field(name="Positions", value="No positions tracked", inline=False)

            embed.set_footer(text="Qwen Wheel Automation")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="analyze", description="Analyze wheel opportunity for a symbol")
    @app_commands.describe(symbol="Stock ticker symbol (e.g., SSYS)")
    async def analyze(self, interaction: discord.Interaction, symbol: str):
        """Analyze wheel opportunity."""
        await interaction.response.defer()

        try:
            symbol = symbol.upper()
            analysis = self.bot.strike_selector.analyze_wheel_opportunity(symbol)

            embed = discord.Embed(
                title=f"Wheel Analysis: {symbol}",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            embed.add_field(
                name="Current Price",
                value=f"${analysis['current_price']:.2f}",
                inline=True,
            )

            if analysis.get("put_opportunity"):
                put = analysis["put_opportunity"]
                embed.add_field(
                    name="Put Opportunity",
                    value=f"**Strike:** ${put['strike']:.2f}\n"
                          f"**Premium:** ${put['premium']:.2f}\n"
                          f"**Delta:** {put['delta']:.3f}\n"
                          f"**DTE:** {put['dte']}\n"
                          f"**Ann. ROI:** {put['annualized_roi']:.1%}",
                    inline=True,
                )
            else:
                embed.add_field(name="Put Opportunity", value="None found", inline=True)

            if analysis.get("call_opportunity"):
                call = analysis["call_opportunity"]
                embed.add_field(
                    name="Call Opportunity",
                    value=f"**Strike:** ${call['strike']:.2f}\n"
                          f"**Premium:** ${call['premium']:.2f}\n"
                          f"**Delta:** {call['delta']:.3f}\n"
                          f"**DTE:** {call['dte']}\n"
                          f"**Ann. ROI:** {call['annualized_roi']:.1%}",
                    inline=True,
                )
            else:
                embed.add_field(name="Call Opportunity", value="None found", inline=True)

            if analysis.get("estimated_wheel_return"):
                embed.add_field(
                    name="Estimated Wheel Return",
                    value=f"**{analysis['estimated_wheel_return']:.1%}** annualized",
                    inline=False,
                )

            embed.set_footer(text="Qwen Wheel Automation")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error analyzing {symbol}: {e}")

    @app_commands.command(name="positions", description="List all wheel positions")
    async def positions(self, interaction: discord.Interaction):
        """List all positions."""
        await interaction.response.defer()

        try:
            positions = self.bot.state_manager.get_all_positions()

            if not positions:
                await interaction.followup.send("No positions tracked.")
                return

            embed = discord.Embed(
                title="Wheel Positions",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )

            for symbol, pos in positions.items():
                value = f"**State:** {pos.state.value}\n"
                value += f"**Premium Collected:** ${pos.total_premium_collected:.2f}\n"
                value += f"**Cycles:** {pos.cycle_count}\n"

                if pos.shares_owned > 0:
                    value += f"**Shares:** {pos.shares_owned}\n"
                    value += f"**Cost Basis:** ${pos.cost_basis:.2f}\n"

                if pos.active_option:
                    opt = pos.active_option
                    value += f"**Active {opt.option_type.upper()}:** ${opt.strike:.2f} ({opt.days_to_expiration} DTE)\n"

                embed.add_field(name=symbol, value=value, inline=True)

            embed.set_footer(text="Qwen Wheel Automation")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="trades", description="Show recent trade history")
    @app_commands.describe(limit="Number of trades to show (default: 10)")
    async def trades(self, interaction: discord.Interaction, limit: int = 10):
        """Show recent trades."""
        await interaction.response.defer()

        try:
            trades = self.bot.state_manager.export_trades()

            if not trades:
                await interaction.followup.send("No trades recorded.")
                return

            recent = trades[-limit:]

            embed = discord.Embed(
                title=f"Recent Trades (Last {len(recent)})",
                color=discord.Color.purple(),
                timestamp=datetime.now(),
            )

            trade_text = ""
            for trade in reversed(recent):
                timestamp = trade["timestamp"][:10]
                action = trade["action"]
                symbol = trade.get("underlying", trade.get("symbol", ""))[:6]
                premium = trade.get("premium", 0)

                emoji = {
                    "sell_to_open": "📉",
                    "buy_to_close": "📈",
                    "assigned": "📋",
                    "called_away": "📤",
                    "expired": "⏰",
                }.get(action, "•")

                trade_text += f"{emoji} `{timestamp}` **{symbol}** {action}"
                if premium:
                    trade_text += f" (${premium:.2f})"
                trade_text += "\n"

            embed.description = trade_text or "No trades"
            embed.set_footer(text="Qwen Wheel Automation")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="briefing", description="Send morning briefing now")
    async def briefing(self, interaction: discord.Interaction):
        """Send morning briefing."""
        await interaction.response.defer()

        try:
            await self.bot._send_morning_briefing()
            await interaction.followup.send("✅ Morning briefing sent to notifications channel!")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="quote", description="Get current quote for a symbol")
    @app_commands.describe(symbol="Stock ticker symbol")
    async def quote(self, interaction: discord.Interaction, symbol: str):
        """Get stock quote."""
        await interaction.response.defer()

        try:
            symbol = symbol.upper()
            quote = self.bot.provider.get_quote(symbol)

            embed = discord.Embed(
                title=f"{symbol} Quote",
                color=discord.Color.teal(),
                timestamp=datetime.now(),
            )

            embed.add_field(name="Price", value=f"${quote.last:.2f}", inline=True)
            embed.add_field(name="Bid", value=f"${quote.bid:.2f}", inline=True)
            embed.add_field(name="Ask", value=f"${quote.ask:.2f}", inline=True)

            if quote.volume:
                embed.add_field(name="Volume", value=f"{quote.volume:,}", inline=True)

            embed.set_footer(text="Qwen Wheel Automation")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="check", description="Run position check now")
    async def check(self, interaction: discord.Interaction):
        """Manually trigger position check."""
        await interaction.response.defer()

        try:
            await interaction.followup.send("🔄 Running position check...")
            await self.bot.position_check_task()
            await interaction.followup.send("✅ Position check complete!")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")


def run_bot():
    """Run the Discord bot."""
    from dotenv import load_dotenv
    load_dotenv()

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not set in environment")
        return

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bot = WheelBot()
    bot.run(token)


if __name__ == "__main__":
    run_bot()
