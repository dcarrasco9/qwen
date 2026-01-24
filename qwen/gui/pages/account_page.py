"""Account page for Alpaca broker integration."""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.gui.theme import COLORS
from qwen.gui.dialogs import CredentialsDialog

logger = logging.getLogger(__name__)

try:
    from qwen.broker.alpaca_broker import AlpacaBroker, ALPACA_AVAILABLE
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-py not installed - account features disabled")


class PositionRow(QFrame):
    """A row showing a portfolio position."""

    def __init__(self, symbol: str, qty: float, avg_price: float, current_price: float,
                 unrealized_pl: float, unrealized_plpc: float, parent=None):
        super().__init__(parent)
        self._setup_ui(symbol, qty, avg_price, current_price, unrealized_pl, unrealized_plpc)

    def _setup_ui(self, symbol: str, qty: float, avg_price: float, current_price: float,
                  unrealized_pl: float, unrealized_plpc: float):
        is_positive = unrealized_pl >= 0

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QFrame:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # Symbol and qty
        left = QVBoxLayout()
        left.setSpacing(2)

        symbol_label = QLabel(symbol)
        symbol_label.setFont(QFont("SF Pro Text", 14, QFont.Weight.Bold))
        symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        left.addWidget(symbol_label)

        qty_label = QLabel(f"{qty:.2f} shares")
        qty_label.setFont(QFont("SF Pro Text", 11))
        qty_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        left.addWidget(qty_label)

        layout.addLayout(left)
        layout.addStretch()

        # Avg price
        avg_layout = QVBoxLayout()
        avg_layout.setSpacing(2)
        avg_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        avg_title = QLabel("Avg Cost")
        avg_title.setFont(QFont("SF Pro Text", 10))
        avg_title.setStyleSheet(f"color: {COLORS['text_muted']};")
        avg_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        avg_layout.addWidget(avg_title)

        avg_val = QLabel(f"${avg_price:.2f}")
        avg_val.setFont(QFont("SF Pro Text", 12))
        avg_val.setStyleSheet(f"color: {COLORS['text']};")
        avg_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        avg_layout.addWidget(avg_val)

        layout.addLayout(avg_layout)

        # Current price
        cur_layout = QVBoxLayout()
        cur_layout.setSpacing(2)
        cur_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        cur_title = QLabel("Current")
        cur_title.setFont(QFont("SF Pro Text", 10))
        cur_title.setStyleSheet(f"color: {COLORS['text_muted']};")
        cur_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        cur_layout.addWidget(cur_title)

        cur_val = QLabel(f"${current_price:.2f}")
        cur_val.setFont(QFont("SF Pro Text", 12))
        cur_val.setStyleSheet(f"color: {COLORS['text']};")
        cur_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        cur_layout.addWidget(cur_val)

        layout.addLayout(cur_layout)

        # Market value
        mv_layout = QVBoxLayout()
        mv_layout.setSpacing(2)
        mv_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        mv_title = QLabel("Value")
        mv_title.setFont(QFont("SF Pro Text", 10))
        mv_title.setStyleSheet(f"color: {COLORS['text_muted']};")
        mv_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        mv_layout.addWidget(mv_title)

        market_value = qty * current_price
        mv_val = QLabel(f"${market_value:,.2f}")
        mv_val.setFont(QFont("SF Pro Text", 12, QFont.Weight.DemiBold))
        mv_val.setStyleSheet(f"color: {COLORS['text']};")
        mv_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        mv_layout.addWidget(mv_val)

        layout.addLayout(mv_layout)

        # P&L
        pl_layout = QVBoxLayout()
        pl_layout.setSpacing(2)
        pl_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        pl_title = QLabel("P&L")
        pl_title.setFont(QFont("SF Pro Text", 10))
        pl_title.setStyleSheet(f"color: {COLORS['text_muted']};")
        pl_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        pl_layout.addWidget(pl_title)

        color = COLORS['positive'] if is_positive else COLORS['negative']
        sign = "+" if is_positive else ""
        pl_val = QLabel(f"{sign}${unrealized_pl:,.2f} ({sign}{unrealized_plpc*100:.1f}%)")
        pl_val.setFont(QFont("SF Pro Text", 12, QFont.Weight.Bold))
        pl_val.setStyleSheet(f"color: {color};")
        pl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        pl_layout.addWidget(pl_val)

        layout.addLayout(pl_layout)


class AccountPage(QWidget):
    """Alpaca account page showing positions and account info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.broker = None
        self.account_info = None
        self.positions = []
        self.api_key = None
        self.secret_key = None
        self.paper = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(20)

        # Header row with connection status and buttons
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        # Connection status indicator
        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(8, 8)
        self.status_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['text_muted']};
                border-radius: 4px;
            }}
        """)
        header_row.addWidget(self.status_indicator)

        self.status_label = QLabel("Not connected")
        self.status_label.setFont(QFont("SF Pro Text", 12))
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        header_row.addWidget(self.status_label)

        header_row.addStretch()

        # Disconnect button
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setFixedHeight(32)
        self.disconnect_btn.setVisible(False)
        self.disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background: none;
                color: {COLORS['negative']};
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self.disconnect_btn.clicked.connect(self._disconnect_alpaca)
        header_row.addWidget(self.disconnect_btn)

        # Connect button
        self.connect_btn = QPushButton("Connect Alpaca")
        self.connect_btn.setFixedHeight(32)
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        self.connect_btn.clicked.connect(self._connect_alpaca)
        header_row.addWidget(self.connect_btn)

        layout.addLayout(header_row)

        # Stats row - simple inline stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(32)

        self.portfolio_stat = self._create_stat("Portfolio Value", "--")
        stats_row.addLayout(self.portfolio_stat)

        self.cash_stat = self._create_stat("Cash", "--")
        stats_row.addLayout(self.cash_stat)

        self.buying_power_stat = self._create_stat("Buying Power", "--")
        stats_row.addLayout(self.buying_power_stat)

        self.day_pl_stat = self._create_stat("Day P&L", "--")
        stats_row.addLayout(self.day_pl_stat)

        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Positions section - simple header
        positions_header = QLabel("Positions")
        positions_header.setFont(QFont("SF Pro Text", 13, QFont.Weight.DemiBold))
        positions_header.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(positions_header)

        # Positions container
        self.positions_container = QVBoxLayout()
        self.positions_container.setSpacing(8)

        # Initial placeholder
        placeholder = QLabel("Connect to Alpaca to view your positions")
        placeholder.setFont(QFont("SF Pro Text", 13))
        placeholder.setStyleSheet(f"color: {COLORS['text_muted']};")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.positions_container.addWidget(placeholder)

        layout.addLayout(self.positions_container)
        layout.addStretch()

    def _create_stat(self, label: str, value: str, color: str = None) -> QVBoxLayout:
        """Create a simple stat display."""
        stat_layout = QVBoxLayout()
        stat_layout.setSpacing(2)

        label_widget = QLabel(label.upper())
        label_widget.setFont(QFont("SF Pro Text", 10))
        label_widget.setStyleSheet(f"color: {COLORS['text_muted']};")
        stat_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setFont(QFont("SF Pro Display", 24, QFont.Weight.Bold))
        value_widget.setStyleSheet(f"color: {color or COLORS['text']};")
        value_widget.setObjectName(f"account_stat_{label.lower().replace(' ', '_')}")
        stat_layout.addWidget(value_widget)

        return stat_layout

    def _connect_alpaca(self):
        """Connect to Alpaca API."""
        if not ALPACA_AVAILABLE:
            QMessageBox.warning(
                self,
                "Alpaca Not Available",
                "alpaca-py is not installed.\n\nInstall with: pip install alpaca-py"
            )
            return

        # If already connected, just refresh
        if self.broker:
            self._refresh_account()
            return

        # Show credentials dialog
        dialog = CredentialsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.api_key, self.secret_key, self.paper = dialog.get_credentials()

        try:
            logger.info(f"Connecting to Alpaca ({'paper' if self.paper else 'live'})")
            self.broker = AlpacaBroker(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
            self._update_connected_state()
            self._refresh_account()
            logger.info("Successfully connected to Alpaca")
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.broker = None
            self.api_key = None
            self.secret_key = None
            QMessageBox.critical(
                self,
                "Connection Failed",
                f"Failed to connect to Alpaca:\n\n{str(e)}"
            )

    def _update_connected_state(self):
        """Update UI to show connected state."""
        mode = "Paper" if self.paper else "Live"

        # Update status indicator
        self.status_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['positive']};
                border-radius: 4px;
            }}
        """)
        self.status_label.setText(f"Connected ({mode})")
        self.status_label.setStyleSheet(f"color: {COLORS['positive']};")

        # Update buttons
        self.connect_btn.setText("Refresh")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """)
        self.disconnect_btn.setVisible(True)

    def _disconnect_alpaca(self):
        """Disconnect from Alpaca."""
        logger.info("Disconnecting from Alpaca")
        self.broker = None
        self.api_key = None
        self.secret_key = None
        self.account_info = None
        self.positions = []

        # Reset status indicator
        self.status_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['text_muted']};
                border-radius: 4px;
            }}
        """)
        self.status_label.setText("Not connected")
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']};")

        # Reset buttons
        self.connect_btn.setText("Connect Alpaca")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        self.disconnect_btn.setVisible(False)

        # Reset stat values
        for name in ["portfolio_value", "cash", "buying_power", "day_p&l"]:
            widget = self.findChild(QLabel, f"account_stat_{name}")
            if widget:
                widget.setText("--")
                widget.setStyleSheet(f"color: {COLORS['text']};")

        # Reset positions display
        self._update_display()

    def _refresh_account(self):
        """Refresh account data from Alpaca."""
        if not self.broker:
            return

        try:
            logger.info("Refreshing account data")
            self.account_info = self.broker.get_account()
            self.positions = self.broker.get_positions()
            self._update_display()
        except Exception as e:
            logger.error(f"Failed to refresh account: {e}")
            QMessageBox.warning(self, "Error", f"Failed to fetch account data:\n{str(e)}")

    def _update_display(self):
        """Update display with current account data."""
        if self.account_info:
            # Update stats using findChild
            portfolio_widget = self.findChild(QLabel, "account_stat_portfolio_value")
            if portfolio_widget:
                portfolio_widget.setText(f"${self.account_info.portfolio_value:,.2f}")

            cash_widget = self.findChild(QLabel, "account_stat_cash")
            if cash_widget:
                cash_widget.setText(f"${self.account_info.cash:,.2f}")

            buying_power_widget = self.findChild(QLabel, "account_stat_buying_power")
            if buying_power_widget:
                buying_power_widget.setText(f"${self.account_info.buying_power:,.2f}")

            day_pl = self.account_info.equity - self.account_info.last_equity
            sign = "+" if day_pl >= 0 else ""
            color = COLORS['positive'] if day_pl >= 0 else COLORS['negative']

            day_pl_widget = self.findChild(QLabel, "account_stat_day_p&l")
            if day_pl_widget:
                day_pl_widget.setText(f"{sign}${day_pl:,.2f}")
                day_pl_widget.setStyleSheet(f"color: {color};")

        # Clear positions container
        while self.positions_container.count():
            item = self.positions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.positions:
            for pos in self.positions:
                row = PositionRow(
                    symbol=pos.symbol,
                    qty=pos.qty,
                    avg_price=pos.avg_entry_price,
                    current_price=pos.current_price,
                    unrealized_pl=pos.unrealized_pl,
                    unrealized_plpc=pos.unrealized_plpc,
                )
                self.positions_container.addWidget(row)
        elif self.broker:
            no_positions = QLabel("No open positions")
            no_positions.setFont(QFont("SF Pro Text", 13))
            no_positions.setStyleSheet(f"color: {COLORS['text_muted']};")
            no_positions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_container.addWidget(no_positions)
        else:
            placeholder = QLabel("Connect to Alpaca to view your positions")
            placeholder.setFont(QFont("SF Pro Text", 13))
            placeholder.setStyleSheet(f"color: {COLORS['text_muted']};")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_container.addWidget(placeholder)
