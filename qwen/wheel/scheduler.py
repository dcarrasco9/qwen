"""
Wheel Strategy Scheduler

Runs the wheel engine on a schedule, checking positions at regular intervals.
"""

import logging
import signal
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from qwen.wheel.config import load_config, WheelConfig
from qwen.wheel.state import WheelStateManager
from qwen.wheel.engine import WheelEngine, SymbolConfig as EngineSymbolConfig
from qwen.wheel.notifications import (
    NotificationHub,
    ConsoleNotifier,
    DiscordNotifier,
    EmailNotifier,
    NotificationLevel,
)

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False


# US Eastern timezone for market hours
ET = ZoneInfo("America/New_York")

# Market hours (regular session)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def is_market_open() -> bool:
    """Check if US stock market is currently open."""
    now = datetime.now(ET)

    # Check weekday (0=Monday, 6=Sunday)
    if now.weekday() >= 5:
        return False

    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


class WheelScheduler:
    """
    Scheduled daemon for wheel strategy execution.

    Runs position checks at configured intervals and sends daily summaries.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        config: Optional[WheelConfig] = None,
    ):
        """
        Initialize the scheduler.

        Args:
            config_path: Path to configuration file
            config: Pre-loaded configuration (overrides config_path)
        """
        if not SCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler is required. Install with: pip install apscheduler"
            )

        # Load configuration
        if config:
            self.config = config
        else:
            self.config = load_config(config_path)

        # Initialize components
        self.state_manager = WheelStateManager()
        self.notifications = self._setup_notifications()

        # Convert config symbols to engine format
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

        # Create engine config
        from qwen.wheel.engine import WheelConfig as EngineConfig
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

        self.engine = WheelEngine(
            state_manager=self.state_manager,
            notifications=self.notifications,
            config=engine_config,
        )

        self.scheduler = BlockingScheduler()
        self._running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _setup_notifications(self) -> NotificationHub:
        """Set up notification backends from config."""
        hub = NotificationHub()

        # Console
        console_config = self.config.notifications.console
        if console_config.get("enabled", True):
            hub.add_backend(ConsoleNotifier(
                min_level=console_config.get("level", "info")
            ))

        # Discord
        discord_config = self.config.notifications.discord
        if discord_config.get("enabled", False):
            hub.add_backend(DiscordNotifier(
                webhook_url=discord_config.get("webhook_url")
            ))

        # Email
        email_config = self.config.notifications.email
        if email_config.get("enabled", False):
            hub.add_backend(EmailNotifier(
                smtp_host=email_config.get("smtp_host"),
                smtp_port=email_config.get("smtp_port", 587),
                username=email_config.get("username"),
                password=email_config.get("password"),
                to_address=email_config.get("to_address"),
            ))

        return hub

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, stopping scheduler...")
        self.stop()

    def _check_all_positions(self):
        """Check all configured symbols."""
        if self.config.market_hours_only and not is_market_open():
            logger.debug("Market closed, skipping position check")
            return

        logger.info("Running scheduled position check...")

        for symbol_config in self.config.symbols:
            if symbol_config.enabled:
                try:
                    self.engine.check_and_execute(symbol_config.symbol)
                except Exception as e:
                    logger.error(f"Error checking {symbol_config.symbol}: {e}")
                    self.notifications.error_alert(
                        f"Error checking {symbol_config.symbol}: {e}",
                        {"symbol": symbol_config.symbol},
                    )

    def _send_daily_summary(self):
        """Send daily summary notification."""
        summary = self.engine.get_status_summary()

        self.notifications.daily_summary(
            positions={"States": str(summary.get("positions_by_state", {}))},
            total_premium=summary.get("total_premium_collected", 0),
            active_count=summary.get("active_positions", 0),
        )

    def start(self):
        """Start the scheduler daemon."""
        logger.info(
            f"Starting wheel scheduler: "
            f"{'PAPER' if self.config.paper_mode else 'LIVE'} mode, "
            f"{len(self.config.symbols)} symbols, "
            f"checking every {self.config.check_interval_minutes} minutes"
        )

        # Schedule position checks
        self.scheduler.add_job(
            self._check_all_positions,
            IntervalTrigger(minutes=self.config.check_interval_minutes),
            id="position_check",
            name="Check all wheel positions",
        )

        # Schedule daily summary at 4:05 PM ET
        self.scheduler.add_job(
            self._send_daily_summary,
            CronTrigger(hour=16, minute=5, timezone=ET),
            id="daily_summary",
            name="Send daily summary",
        )

        # Run initial check
        self._check_all_positions()

        # Send startup notification
        self.notifications.notify(
            f"Wheel automation started - monitoring {len(self.config.symbols)} symbols",
            level=NotificationLevel.INFO,
            title="Wheel Scheduler Started",
            data={
                "Mode": "PAPER" if self.config.paper_mode else "LIVE",
                "Check Interval": f"{self.config.check_interval_minutes} minutes",
                "Symbols": ", ".join(s.symbol for s in self.config.symbols if s.enabled),
            },
        )

        self._running = True

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self):
        """Stop the scheduler daemon."""
        if self._running:
            logger.info("Stopping wheel scheduler...")
            self._running = False

            self.notifications.notify(
                "Wheel automation stopped",
                level=NotificationLevel.WARNING,
                title="Wheel Scheduler Stopped",
            )

            self.scheduler.shutdown(wait=False)
            sys.exit(0)

    def run_once(self, symbol: Optional[str] = None):
        """
        Run a single check cycle (for testing or manual execution).

        Args:
            symbol: Specific symbol to check (None = all symbols)
        """
        if symbol:
            self.engine.check_and_execute(symbol)
        else:
            self._check_all_positions()


def run_daemon(config_path: Optional[Path] = None):
    """
    Entry point to run the wheel scheduler daemon.

    Args:
        config_path: Path to configuration file
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scheduler = WheelScheduler(config_path=config_path)
    scheduler.start()


if __name__ == "__main__":
    run_daemon()
