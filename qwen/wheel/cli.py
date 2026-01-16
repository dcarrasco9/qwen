"""
Wheel Strategy CLI

Command-line interface for wheel automation:
- Start/stop the daemon
- Check status
- Manual execution
- View trade history
"""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import click
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

from qwen.wheel.config import load_config, create_default_config
from qwen.wheel.state import WheelStateManager, WheelState
from qwen.wheel.scheduler import WheelScheduler, is_market_open


def setup_logging(verbose: bool = False):
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


if CLICK_AVAILABLE:
    @click.group()
    @click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
    def wheel(verbose: bool):
        """Wheel strategy automation commands."""
        setup_logging(verbose)

    @wheel.command()
    @click.option(
        "--config", "-c",
        type=click.Path(exists=True, path_type=Path),
        help="Path to config file",
    )
    def start(config: Optional[Path]):
        """Start the wheel automation daemon."""
        click.echo("Starting wheel automation daemon...")
        click.echo("Press Ctrl+C to stop")
        click.echo()

        scheduler = WheelScheduler(config_path=config)
        scheduler.start()

    @wheel.command()
    def status():
        """Show current wheel positions status."""
        state_manager = WheelStateManager()
        positions = state_manager.get_all_positions()
        summary = state_manager.get_summary()

        click.echo()
        click.echo("=" * 60)
        click.echo("WHEEL STRATEGY STATUS")
        click.echo("=" * 60)
        click.echo()

        # Market status
        market_status = "OPEN" if is_market_open() else "CLOSED"
        click.echo(f"Market: {market_status}")
        click.echo()

        # Summary
        click.echo(f"Total Positions: {summary['total_positions']}")
        click.echo(f"Active Positions: {summary['active_positions']}")
        click.echo(f"Total Premium Collected: ${summary['total_premium_collected']:.2f}")
        click.echo(f"Cycles Completed: {summary['total_cycles_completed']}")
        click.echo()

        # Position details
        if positions:
            click.echo("-" * 60)
            click.echo("POSITIONS")
            click.echo("-" * 60)

            for symbol, pos in sorted(positions.items()):
                state_color = {
                    WheelState.IDLE: "white",
                    WheelState.PUT_OPEN: "yellow",
                    WheelState.HOLDING_SHARES: "blue",
                    WheelState.CALL_OPEN: "cyan",
                }.get(pos.state, "white")

                click.echo()
                click.secho(f"{symbol}", fg="green", bold=True)
                click.echo(f"  State: ", nl=False)
                click.secho(pos.state.value, fg=state_color)

                if pos.shares_owned > 0:
                    click.echo(f"  Shares: {pos.shares_owned}")
                    click.echo(f"  Cost Basis: ${pos.cost_basis:.2f}")
                    click.echo(f"  Effective Basis: ${pos.effective_cost_basis:.2f}")

                if pos.active_option:
                    opt = pos.active_option
                    click.echo(f"  Active Option: {opt.option_type.upper()}")
                    click.echo(f"    Strike: ${opt.strike:.2f}")
                    click.echo(f"    DTE: {opt.days_to_expiration}")
                    click.echo(f"    Premium: ${opt.premium:.2f}")

                click.echo(f"  Premium Collected: ${pos.total_premium_collected:.2f}")
                click.echo(f"  Cycles: {pos.cycle_count}")

        else:
            click.echo("No positions tracked yet.")

        click.echo()

    @wheel.command()
    @click.argument("symbol")
    @click.option(
        "--config", "-c",
        type=click.Path(exists=True, path_type=Path),
        help="Path to config file",
    )
    def check(symbol: str, config: Optional[Path]):
        """Manually check and execute for a symbol."""
        click.echo(f"Checking {symbol}...")

        scheduler = WheelScheduler(config_path=config)
        scheduler.run_once(symbol.upper())

        click.echo("Done.")

    @wheel.command()
    @click.option(
        "--config", "-c",
        type=click.Path(exists=True, path_type=Path),
        help="Path to config file",
    )
    def check_all(config: Optional[Path]):
        """Check all configured symbols once."""
        click.echo("Checking all symbols...")

        scheduler = WheelScheduler(config_path=config)
        scheduler.run_once()

        click.echo("Done.")

    @wheel.command()
    @click.option("--symbol", "-s", help="Filter by symbol")
    @click.option("--limit", "-n", default=20, help="Number of trades to show")
    def trades(symbol: Optional[str], limit: int):
        """Show trade history."""
        state_manager = WheelStateManager()
        trades_list = state_manager.export_trades(symbol)

        click.echo()
        click.echo("=" * 80)
        click.echo("TRADE HISTORY")
        click.echo("=" * 80)
        click.echo()

        if not trades_list:
            click.echo("No trades recorded yet.")
            return

        # Show most recent trades
        recent = trades_list[-limit:]

        for trade in recent:
            timestamp = trade["timestamp"][:19]  # Trim microseconds
            action = trade["action"]
            sym = trade.get("underlying", trade.get("symbol", ""))
            opt_type = trade.get("option_type", "")
            strike = trade.get("strike")
            premium = trade.get("premium", 0)

            # Color code by action
            if "sell" in action:
                color = "green"
            elif "assigned" in action or "called" in action:
                color = "yellow"
            elif "expired" in action:
                color = "cyan"
            else:
                color = "white"

            line = f"{timestamp} | {action:15} | {sym:6}"
            if opt_type:
                line += f" | {opt_type:4}"
            if strike:
                line += f" | ${strike:7.2f}"
            if premium:
                line += f" | ${premium:8.2f}"

            click.secho(line, fg=color)

        click.echo()
        click.echo(f"Showing {len(recent)} of {len(trades_list)} trades")

    @wheel.command()
    @click.argument("symbol")
    def reset(symbol: str):
        """Reset a symbol's wheel position to IDLE."""
        state_manager = WheelStateManager()

        if click.confirm(f"Reset {symbol} to IDLE state? This cannot be undone."):
            state_manager.remove_position(symbol.upper())
            click.echo(f"{symbol} position reset.")
        else:
            click.echo("Cancelled.")

    @wheel.command()
    @click.option(
        "--path", "-p",
        type=click.Path(path_type=Path),
        default=Path("wheel_config.yaml"),
        help="Path for config file",
    )
    def init(path: Path):
        """Create a default configuration file."""
        if path.exists():
            if not click.confirm(f"{path} already exists. Overwrite?"):
                click.echo("Cancelled.")
                return

        create_default_config(path)
        click.echo(f"Created default config at {path}")
        click.echo()
        click.echo("Edit the file to configure your symbols and settings.")
        click.echo("Then run: python -m qwen.wheel.cli start")

    @wheel.command()
    @click.argument("symbol")
    def analyze(symbol: str):
        """Analyze wheel opportunity for a symbol."""
        from qwen.wheel.strike_selector import StrikeSelector

        click.echo(f"Analyzing {symbol}...")
        click.echo()

        selector = StrikeSelector()

        try:
            analysis = selector.analyze_wheel_opportunity(symbol.upper())

            click.echo("=" * 60)
            click.secho(f"WHEEL ANALYSIS: {symbol.upper()}", fg="green", bold=True)
            click.echo("=" * 60)
            click.echo()

            click.echo(f"Current Price: ${analysis['current_price']:.2f}")
            click.echo()

            if analysis.get("put_opportunity"):
                put = analysis["put_opportunity"]
                click.secho("PUT OPPORTUNITY", fg="yellow", bold=True)
                click.echo(f"  Strike: ${put['strike']:.2f}")
                click.echo(f"  Premium: ${put['premium']:.2f}")
                click.echo(f"  Delta: {put['delta']:.3f}")
                click.echo(f"  DTE: {put['dte']}")
                click.echo(f"  Annualized ROI: {put['annualized_roi']:.1%}")
                click.echo()
            else:
                click.echo("No suitable put found.")
                click.echo()

            if analysis.get("call_opportunity"):
                call = analysis["call_opportunity"]
                click.secho("CALL OPPORTUNITY", fg="cyan", bold=True)
                click.echo(f"  Strike: ${call['strike']:.2f}")
                click.echo(f"  Premium: ${call['premium']:.2f}")
                click.echo(f"  Delta: {call['delta']:.3f}")
                click.echo(f"  DTE: {call['dte']}")
                click.echo(f"  Annualized ROI: {call['annualized_roi']:.1%}")
                click.echo()
            else:
                click.echo("No suitable call found (or below cost basis).")
                click.echo()

            if analysis.get("estimated_wheel_return"):
                click.secho(
                    f"Estimated Wheel Return: {analysis['estimated_wheel_return']:.1%} annualized",
                    fg="green",
                    bold=True,
                )

        except Exception as e:
            click.secho(f"Error analyzing {symbol}: {e}", fg="red")

    # Discord commands
    @wheel.group()
    def discord():
        """Discord notification commands."""
        pass

    @discord.command(name="briefing")
    def discord_briefing():
        """Send morning briefing to Discord."""
        from qwen.wheel.discord_reports import DiscordReporter

        click.echo("Sending morning briefing to Discord...")
        reporter = DiscordReporter()
        if reporter.send_morning_briefing():
            click.secho("✓ Morning briefing sent!", fg="green")
        else:
            click.secho("✗ Failed to send", fg="red")

    @discord.command(name="summary")
    def discord_summary():
        """Send daily summary to Discord."""
        from qwen.wheel.discord_reports import DiscordReporter

        click.echo("Sending daily summary to Discord...")
        reporter = DiscordReporter()
        if reporter.send_daily_summary():
            click.secho("✓ Daily summary sent!", fg="green")
        else:
            click.secho("✗ Failed to send", fg="red")

    @discord.command(name="weekly")
    def discord_weekly():
        """Send weekly report to Discord."""
        from qwen.wheel.discord_reports import DiscordReporter

        click.echo("Sending weekly report to Discord...")
        reporter = DiscordReporter()
        if reporter.send_weekly_report():
            click.secho("✓ Weekly report sent!", fg="green")
        else:
            click.secho("✗ Failed to send", fg="red")

    @discord.command(name="analyze")
    @click.argument("symbol")
    def discord_analyze(symbol: str):
        """Send wheel analysis to Discord."""
        from qwen.wheel.discord_reports import DiscordReporter

        click.echo(f"Sending {symbol} analysis to Discord...")
        reporter = DiscordReporter()
        if reporter.send_analysis(symbol):
            click.secho(f"✓ {symbol} analysis sent!", fg="green")
        else:
            click.secho("✗ Failed to send", fg="red")

    @discord.command(name="position")
    @click.argument("symbol")
    def discord_position(symbol: str):
        """Send position update to Discord."""
        from qwen.wheel.discord_reports import DiscordReporter

        click.echo(f"Sending {symbol} position to Discord...")
        reporter = DiscordReporter()
        if reporter.send_position_update(symbol):
            click.secho(f"✓ {symbol} position sent!", fg="green")
        else:
            click.secho("✗ Failed to send", fg="red")

    @discord.command(name="alert")
    @click.argument("symbol")
    @click.argument("price", type=float)
    @click.option("--above", "direction", flag_value="above", help="Alert when price goes above")
    @click.option("--below", "direction", flag_value="below", default=True, help="Alert when price goes below")
    def discord_alert(symbol: str, price: float, direction: str):
        """Add a price alert (sends to Discord when triggered)."""
        from qwen.wheel.discord_reports import DiscordReporter

        reporter = DiscordReporter()
        reporter.add_price_alert(symbol, price, direction)
        click.secho(f"✓ Alert added: {symbol} {direction} ${price:.2f}", fg="green")
        click.echo("Note: Alerts are checked when the daemon runs")

    def main():
        """Entry point for CLI."""
        wheel()

else:
    # Fallback if click is not available
    def main():
        print("Click library is required for CLI. Install with: pip install click")
        print()
        print("You can still use the wheel module programmatically:")
        print("  from qwen.wheel import WheelEngine, WheelStateManager")
        sys.exit(1)


if __name__ == "__main__":
    main()
