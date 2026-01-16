"""
Wheel Strategy Configuration Loader

Loads configuration from YAML files with environment variable expansion.
"""

import os
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class SymbolConfig:
    """Configuration for a single symbol."""

    symbol: str
    enabled: bool = True
    target_put_delta: float = 0.25
    target_call_delta: float = 0.30
    min_dte: int = 25
    max_dte: int = 45
    min_premium: float = 0.30
    max_positions: int = 1


@dataclass
class NotificationConfig:
    """Notification backend configuration."""

    console: dict = field(default_factory=lambda: {"enabled": True, "level": "info"})
    discord: dict = field(default_factory=lambda: {"enabled": False, "webhook_url": None})
    email: dict = field(default_factory=lambda: {"enabled": False})


@dataclass
class SafetyConfig:
    """Safety and risk management configuration."""

    max_loss_per_position: float = 500
    stop_loss_percent: float = 0.50
    min_buying_power_reserve: float = 5000
    roll_dte_threshold: int = 5


@dataclass
class WheelConfig:
    """Complete wheel strategy configuration."""

    symbols: list[SymbolConfig] = field(default_factory=list)
    check_interval_minutes: int = 60
    market_hours_only: bool = True
    max_total_capital: float = 50000
    paper_mode: bool = True
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


def _expand_env_vars(value: str) -> str:
    """Expand environment variables in a string value."""
    if not isinstance(value, str):
        return value

    # Match ${VAR} or $VAR patterns
    pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'

    def replace(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    return re.sub(pattern, replace, value)


def _expand_env_vars_recursive(obj):
    """Recursively expand environment variables in a data structure."""
    if isinstance(obj, dict):
        return {k: _expand_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars_recursive(item) for item in obj]
    elif isinstance(obj, str):
        return _expand_env_vars(obj)
    return obj


def load_config(config_path: Optional[Path] = None) -> WheelConfig:
    """
    Load wheel configuration from YAML file.

    Args:
        config_path: Path to YAML config file. If None, uses default locations.

    Returns:
        WheelConfig object

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If YAML parsing fails
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for configuration. Install with: pip install pyyaml"
        )

    # Default config locations
    if config_path is None:
        search_paths = [
            Path.cwd() / "wheel_config.yaml",
            Path.cwd() / "wheel_config.yml",
            Path.home() / ".qwen" / "wheel_config.yaml",
        ]
        for path in search_paths:
            if path.exists():
                config_path = path
                break

        if config_path is None:
            logger.warning("No config file found, using defaults")
            return WheelConfig()

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info(f"Loading config from {config_path}")

    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f)

    if not raw_config:
        return WheelConfig()

    # Expand environment variables
    config_data = _expand_env_vars_recursive(raw_config)

    # Parse symbols
    symbols = []
    for sym_data in config_data.get("symbols", []):
        symbols.append(SymbolConfig(
            symbol=sym_data["symbol"],
            enabled=sym_data.get("enabled", True),
            target_put_delta=sym_data.get("target_put_delta", 0.25),
            target_call_delta=sym_data.get("target_call_delta", 0.30),
            min_dte=sym_data.get("min_dte", 25),
            max_dte=sym_data.get("max_dte", 45),
            min_premium=sym_data.get("min_premium", 0.30),
            max_positions=sym_data.get("max_positions", 1),
        ))

    # Parse global settings
    global_settings = config_data.get("global", {})

    # Parse notifications
    notif_data = config_data.get("notifications", {})
    notifications = NotificationConfig(
        console=notif_data.get("console", {"enabled": True, "level": "info"}),
        discord=notif_data.get("discord", {"enabled": False}),
        email=notif_data.get("email", {"enabled": False}),
    )

    # Parse safety settings
    safety_data = config_data.get("safety", {})
    safety = SafetyConfig(
        max_loss_per_position=safety_data.get("max_loss_per_position", 500),
        stop_loss_percent=safety_data.get("stop_loss_percent", 0.50),
        min_buying_power_reserve=safety_data.get("min_buying_power_reserve", 5000),
        roll_dte_threshold=safety_data.get("roll_dte_threshold", 5),
    )

    return WheelConfig(
        symbols=symbols,
        check_interval_minutes=global_settings.get("check_interval_minutes", 60),
        market_hours_only=global_settings.get("market_hours_only", True),
        max_total_capital=global_settings.get("max_total_capital", 50000),
        paper_mode=global_settings.get("paper_mode", True),
        notifications=notifications,
        safety=safety,
    )


def create_default_config(path: Path) -> None:
    """
    Create a default configuration file.

    Args:
        path: Path where to create the config file
    """
    default_config = """# Wheel Strategy Configuration
# =============================

# Symbols to run wheel strategy on
symbols:
  - symbol: SSYS
    enabled: true
    target_put_delta: 0.25    # 25-delta puts
    target_call_delta: 0.30   # 30-delta calls
    min_dte: 25               # Minimum days to expiration
    max_dte: 45               # Maximum days to expiration
    min_premium: 0.30         # Minimum premium per share
    max_positions: 1          # Max concurrent wheels on this symbol

  - symbol: RKLB
    enabled: true
    target_put_delta: 0.20
    target_call_delta: 0.25
    min_dte: 30
    max_dte: 45
    min_premium: 0.25
    max_positions: 1

# Global settings
global:
  check_interval_minutes: 60  # How often to check positions
  market_hours_only: true     # Only execute during market hours
  max_total_capital: 50000    # Maximum capital to deploy
  paper_mode: true            # Start with paper trading!

# Notification settings
notifications:
  console:
    enabled: true
    level: info               # debug, info, warning, error

  discord:
    enabled: false
    webhook_url: ${DISCORD_WEBHOOK_URL}

  email:
    enabled: false
    smtp_host: smtp.gmail.com
    smtp_port: 587
    username: ${EMAIL_USERNAME}
    password: ${EMAIL_PASSWORD}
    to_address: your@email.com

# Safety settings
safety:
  max_loss_per_position: 500  # Max loss before closing position
  stop_loss_percent: 0.50     # Close if option doubles against us
  min_buying_power_reserve: 5000  # Always keep this much cash
  roll_dte_threshold: 5       # Consider rolling at this DTE
"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(default_config)

    logger.info(f"Created default config at {path}")
