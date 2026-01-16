"""
Discord Bot for Wheel Strategy

Provides slash commands for interacting with the wheel automation:
- /status - Show current positions
- /analyze <symbol> - Analyze wheel opportunity
- /positions - List all positions
- /trades - Show recent trades
- /briefing - Send morning briefing now
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from qwen.wheel.state import WheelStateManager, WheelState
from qwen.wheel.strike_selector import StrikeSelector
from qwen.wheel.config import load_config
from qwen.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)


class WheelBot(commands.Bot):
    """Discord bot for wheel strategy interactions."""

    def __init__(self):
        intents = discord.Intents.default()
        # Note: message_content intent not needed for slash commands

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Qwen Wheel Strategy Bot",
        )

        self.state_manager = WheelStateManager()
        self.strike_selector = StrikeSelector()
        self.config = load_config()
        self.provider = YahooDataProvider()

    async def setup_hook(self):
        """Set up slash commands."""
        await self.add_cog(WheelCommands(self))
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Bot logged in as {self.user}")
        print(f"Bot logged in as {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("Slash commands available:")
        print("  /status - Show wheel status")
        print("  /analyze <symbol> - Analyze opportunity")
        print("  /positions - List positions")
        print("  /trades - Show recent trades")
        print("  /briefing - Send morning briefing")


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

            # Add position details
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
            positions = self.bot.state_manager.get_all_positions()
            summary = self.bot.state_manager.get_summary()

            embed = discord.Embed(
                title="Morning Briefing",
                color=discord.Color.orange(),
                timestamp=datetime.now(),
            )

            # Active positions
            active_text = ""
            opportunities_text = ""

            for sym_config in self.bot.config.symbols:
                if not sym_config.enabled:
                    continue

                symbol = sym_config.symbol
                pos = positions.get(symbol)

                try:
                    quote = self.bot.provider.get_quote(symbol)
                    price = quote.last

                    if pos and pos.state != WheelState.IDLE:
                        if pos.active_option:
                            opt = pos.active_option
                            active_text += f"**{symbol}**: ${price:.2f} | {opt.option_type.upper()} ${opt.strike:.2f} | {opt.days_to_expiration} DTE\n"
                    else:
                        analysis = self.bot.strike_selector.analyze_wheel_opportunity(symbol)
                        if analysis.get("put_opportunity"):
                            put = analysis["put_opportunity"]
                            opportunities_text += f"**{symbol}**: ${price:.2f} | Put ${put['strike']:.2f} @ ${put['premium']:.2f} ({put['annualized_roi']:.0%})\n"

                except Exception as e:
                    logger.warning(f"Error getting data for {symbol}: {e}")

            embed.add_field(
                name="Active Positions",
                value=active_text or "None",
                inline=False,
            )

            embed.add_field(
                name="Opportunities",
                value=opportunities_text or "No new opportunities",
                inline=False,
            )

            embed.add_field(
                name="Summary",
                value=f"**Total Premium:** ${summary.get('total_premium_collected', 0):.2f}\n"
                      f"**Active:** {summary.get('active_positions', 0)}",
                inline=False,
            )

            embed.set_footer(text="Qwen Wheel Automation")

            await interaction.followup.send(embed=embed)

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
