"""
Multi-channel Notification System for Wheel Automation

Supports:
- Console logging
- Discord webhooks
- Email (SMTP)
"""

import json
import logging
import os
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class NotificationLevel:
    """Notification severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Notification:
    """A notification message."""

    message: str
    level: str = NotificationLevel.INFO
    title: Optional[str] = None
    data: Optional[dict] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class NotifierBackend(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """
        Send a notification.

        Args:
            notification: The notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the backend is properly configured."""
        pass


class ConsoleNotifier(NotifierBackend):
    """Console/logging notification backend."""

    def __init__(self, min_level: str = NotificationLevel.INFO):
        self.min_level = min_level
        self._level_order = {
            NotificationLevel.DEBUG: 0,
            NotificationLevel.INFO: 1,
            NotificationLevel.WARNING: 2,
            NotificationLevel.ERROR: 3,
            NotificationLevel.CRITICAL: 4,
        }

    def is_configured(self) -> bool:
        return True

    def send(self, notification: Notification) -> bool:
        if self._level_order.get(notification.level, 1) < self._level_order.get(self.min_level, 1):
            return True  # Filtered by level, but not an error

        timestamp = notification.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        level = notification.level.upper()

        if notification.title:
            print(f"[{timestamp}] [{level}] {notification.title}: {notification.message}")
        else:
            print(f"[{timestamp}] [{level}] {notification.message}")

        if notification.data:
            for key, value in notification.data.items():
                print(f"  {key}: {value}")

        return True


class DiscordNotifier(NotifierBackend):
    """Discord webhook notification backend."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _build_embed(self, notification: Notification) -> dict:
        """Build Discord embed object."""
        color_map = {
            NotificationLevel.DEBUG: 0x808080,  # Gray
            NotificationLevel.INFO: 0x3498DB,  # Blue
            NotificationLevel.WARNING: 0xF39C12,  # Orange
            NotificationLevel.ERROR: 0xE74C3C,  # Red
            NotificationLevel.CRITICAL: 0x8E44AD,  # Purple
        }

        embed = {
            "title": notification.title or "Wheel Automation",
            "description": notification.message,
            "color": color_map.get(notification.level, 0x3498DB),
            "timestamp": notification.timestamp.isoformat(),
            "footer": {"text": "Qwen Wheel Automation"},
        }

        if notification.data:
            fields = []
            for key, value in notification.data.items():
                fields.append({
                    "name": key,
                    "value": str(value),
                    "inline": True,
                })
            embed["fields"] = fields

        return embed

    def send(self, notification: Notification) -> bool:
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        payload = {
            "embeds": [self._build_embed(notification)],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=10) as response:
                return response.status == 204

        except URLError as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False


class EmailNotifier(NotifierBackend):
    """Email (SMTP) notification backend."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port
        self.username = username or os.environ.get("EMAIL_USERNAME")
        self.password = password or os.environ.get("EMAIL_PASSWORD")
        self.from_address = from_address or self.username
        self.to_address = to_address or os.environ.get("EMAIL_TO_ADDRESS")
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        return all([
            self.smtp_host,
            self.username,
            self.password,
            self.from_address,
            self.to_address,
        ])

    def send(self, notification: Notification) -> bool:
        if not self.is_configured():
            logger.warning("Email not properly configured")
            return False

        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = notification.title or f"Wheel Alert: {notification.level.upper()}"
        msg["From"] = self.from_address
        msg["To"] = self.to_address

        # Plain text version
        text_body = f"{notification.message}\n\n"
        if notification.data:
            text_body += "Details:\n"
            for key, value in notification.data.items():
                text_body += f"  {key}: {value}\n"
        text_body += f"\nTimestamp: {notification.timestamp.isoformat()}"

        # HTML version
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #333;">{notification.title or 'Wheel Automation Alert'}</h2>
            <p style="font-size: 16px;">{notification.message}</p>
        """

        if notification.data:
            html_body += "<table style='border-collapse: collapse; margin-top: 10px;'>"
            for key, value in notification.data.items():
                html_body += f"""
                <tr>
                    <td style='padding: 5px 10px; border: 1px solid #ddd; font-weight: bold;'>{key}</td>
                    <td style='padding: 5px 10px; border: 1px solid #ddd;'>{value}</td>
                </tr>
                """
            html_body += "</table>"

        html_body += f"""
            <p style="color: #666; font-size: 12px; margin-top: 20px;">
                Timestamp: {notification.timestamp.isoformat()}<br>
                Sent by Qwen Wheel Automation
            </p>
        </body>
        </html>
        """

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_address, self.to_address, msg.as_string())
            return True

        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")
            return False
        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False


class NotificationHub:
    """
    Central hub for sending notifications to multiple backends.

    Manages multiple notification backends and routes messages appropriately.
    """

    def __init__(self):
        self.backends: list[NotifierBackend] = []

    def add_backend(self, backend: NotifierBackend) -> "NotificationHub":
        """Add a notification backend."""
        if backend.is_configured():
            self.backends.append(backend)
            logger.info(f"Added notification backend: {backend.__class__.__name__}")
        else:
            logger.warning(f"Backend not configured: {backend.__class__.__name__}")
        return self

    def notify(
        self,
        message: str,
        level: str = NotificationLevel.INFO,
        title: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> int:
        """
        Send a notification to all configured backends.

        Args:
            message: The notification message
            level: Notification level (info, warning, error, etc.)
            title: Optional title
            data: Optional additional data

        Returns:
            Number of backends that successfully sent the notification
        """
        notification = Notification(
            message=message,
            level=level,
            title=title,
            data=data,
        )

        success_count = 0
        for backend in self.backends:
            try:
                if backend.send(notification):
                    success_count += 1
            except Exception as e:
                logger.error(f"Backend {backend.__class__.__name__} failed: {e}")

        return success_count

    def trade_alert(
        self,
        action: str,
        symbol: str,
        details: dict,
    ) -> int:
        """
        Send a trade alert notification.

        Args:
            action: Trade action (e.g., "SELL PUT", "BUY TO CLOSE")
            symbol: Stock ticker
            details: Trade details (strike, premium, etc.)

        Returns:
            Number of successful sends
        """
        title = f"Trade: {action} {symbol}"
        message = f"Executed {action} on {symbol}"

        return self.notify(
            message=message,
            level=NotificationLevel.INFO,
            title=title,
            data=details,
        )

    def assignment_alert(
        self,
        symbol: str,
        option_type: str,
        strike: float,
        shares: int,
    ) -> int:
        """
        Send an assignment notification.

        Args:
            symbol: Stock ticker
            option_type: 'put' or 'call'
            strike: Strike price
            shares: Number of shares

        Returns:
            Number of successful sends
        """
        if option_type == "put":
            title = f"Assignment: {symbol} Put"
            message = f"Put assigned - acquired {shares} shares at ${strike:.2f}"
        else:
            title = f"Called Away: {symbol}"
            message = f"Call assigned - sold {shares} shares at ${strike:.2f}"

        return self.notify(
            message=message,
            level=NotificationLevel.WARNING,
            title=title,
            data={
                "Symbol": symbol,
                "Type": option_type.upper(),
                "Strike": f"${strike:.2f}",
                "Shares": shares,
            },
        )

    def error_alert(
        self,
        error: str,
        context: Optional[dict] = None,
    ) -> int:
        """
        Send an error notification.

        Args:
            error: Error message
            context: Additional context

        Returns:
            Number of successful sends
        """
        return self.notify(
            message=error,
            level=NotificationLevel.ERROR,
            title="Wheel Automation Error",
            data=context,
        )

    def daily_summary(
        self,
        positions: dict,
        total_premium: float,
        active_count: int,
    ) -> int:
        """
        Send a daily summary notification.

        Args:
            positions: Position summary data
            total_premium: Total premium collected
            active_count: Number of active positions

        Returns:
            Number of successful sends
        """
        return self.notify(
            message=f"{active_count} active positions, ${total_premium:.2f} total premium collected",
            level=NotificationLevel.INFO,
            title="Daily Wheel Summary",
            data={
                "Active Positions": active_count,
                "Total Premium": f"${total_premium:.2f}",
                **positions,
            },
        )


def create_notification_hub(config: dict) -> NotificationHub:
    """
    Create a NotificationHub from configuration.

    Args:
        config: Configuration dictionary with backend settings

    Returns:
        Configured NotificationHub
    """
    hub = NotificationHub()

    # Console
    if config.get("console", {}).get("enabled", True):
        level = config.get("console", {}).get("level", NotificationLevel.INFO)
        hub.add_backend(ConsoleNotifier(min_level=level))

    # Discord
    discord_config = config.get("discord", {})
    if discord_config.get("enabled", False):
        hub.add_backend(DiscordNotifier(
            webhook_url=discord_config.get("webhook_url"),
        ))

    # Email
    email_config = config.get("email", {})
    if email_config.get("enabled", False):
        hub.add_backend(EmailNotifier(
            smtp_host=email_config.get("smtp_host"),
            smtp_port=email_config.get("smtp_port", 587),
            username=email_config.get("username"),
            password=email_config.get("password"),
            from_address=email_config.get("from_address"),
            to_address=email_config.get("to_address"),
        ))

    return hub
