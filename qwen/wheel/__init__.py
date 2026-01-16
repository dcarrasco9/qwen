"""
Wheel Strategy Automation Module

Provides fully automated wheel strategy execution:
- State persistence across sessions
- Delta-based strike selection
- Multi-channel notifications (console, Discord, email)
- Scheduled daemon for continuous monitoring
- CLI for manual control

Usage:
    # Start the daemon
    python -m qwen.wheel.cli start

    # Check status
    python -m qwen.wheel.cli status

    # Manual check for a symbol
    python -m qwen.wheel.cli check SSYS

    # Analyze a symbol
    python -m qwen.wheel.cli analyze SSYS
"""

from qwen.wheel.state import (
    WheelPosition,
    WheelStateManager,
    WheelState,
    OptionInfo,
    Trade,
)
from qwen.wheel.strike_selector import StrikeSelector, StrikeCandidate
from qwen.wheel.notifications import (
    NotificationHub,
    ConsoleNotifier,
    DiscordNotifier,
    EmailNotifier,
    create_notification_hub,
)
from qwen.wheel.engine import WheelEngine
from qwen.wheel.config import load_config, WheelConfig, SymbolConfig
from qwen.wheel.scheduler import WheelScheduler

__all__ = [
    # State management
    "WheelPosition",
    "WheelStateManager",
    "WheelState",
    "OptionInfo",
    "Trade",
    # Strike selection
    "StrikeSelector",
    "StrikeCandidate",
    # Notifications
    "NotificationHub",
    "ConsoleNotifier",
    "DiscordNotifier",
    "EmailNotifier",
    "create_notification_hub",
    # Engine
    "WheelEngine",
    # Configuration
    "load_config",
    "WheelConfig",
    "SymbolConfig",
    # Scheduler
    "WheelScheduler",
]
