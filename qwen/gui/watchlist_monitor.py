"""
Qwen Watchlist Monitor - Standalone Desktop GUI

A PySide6-based application for monitoring watchlist stocks with real-time prices.

Run with: python -m qwen.gui.watchlist_monitor
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QFrame,
    QProgressBar,
    QSpacerItem,
    QSizePolicy,
    QToolTip,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QPalette, QColor, QShortcut, QKeySequence

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from qwen.broker.alpaca_broker import AlpacaBroker, ALPACA_AVAILABLE
except ImportError:
    ALPACA_AVAILABLE = False

from qwen.watchlist import Watchlist, WatchlistStock, Sector, RiskLevel
from qwen.gui.theme import theme, COLORS, SECTOR_COLORS, Dimensions

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PriceWorker(QObject):
    """Worker for fetching prices in background thread."""

    prices_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, tickers: list[str]):
        super().__init__()
        self.tickers = tickers
        self._running = True

    def fetch_prices(self):
        if not YFINANCE_AVAILABLE:
            self.error.emit("yfinance not installed")
            return

        if not self._running:
            return

        try:
            prices = {}
            tickers_str = " ".join(self.tickers)
            data = yf.download(
                tickers_str,
                period="2d",
                progress=False,
                group_by='ticker',
                threads=True
            )

            for ticker in self.tickers:
                if not self._running:
                    return
                try:
                    if len(self.tickers) == 1:
                        ticker_data = data
                    else:
                        ticker_data = data[ticker]

                    if ticker_data.empty or len(ticker_data) < 1:
                        logger.warning(f"No data available for {ticker}")
                        continue

                    current = float(ticker_data['Close'].iloc[-1])

                    if len(ticker_data) >= 2:
                        prev_close = float(ticker_data['Close'].iloc[-2])
                    else:
                        prev_close = float(ticker_data['Open'].iloc[-1])

                    change = current - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    prices[ticker] = {
                        "price": current,
                        "change": change,
                        "change_pct": change_pct,
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch price for {ticker}: {e}")
                    continue

            if self._running:
                self.prices_ready.emit(prices)

        except Exception as e:
            if self._running:
                self.error.emit(str(e))

    def stop(self):
        self._running = False


class StatCard(QFrame):
    """A clean stat card widget."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(parent)
        self._setup_ui(title, value, subtitle)

    def _setup_ui(self, title: str, value: str, subtitle: str):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)

        self.title_label = QLabel(title.upper())
        self.title_label.setFont(QFont("SF Pro Text", 10, QFont.Weight.Medium))
        self.title_label.setStyleSheet(f"color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("SF Pro Display", 28, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(self.value_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setFont(QFont("SF Pro Text", 11))
            self.subtitle_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        else:
            self.value_label.setStyleSheet(f"color: {COLORS['text']};")

    def set_subtitle(self, text: str):
        if self.subtitle_label:
            self.subtitle_label.setText(text)


class SectorBar(QFrame):
    """A horizontal bar showing sector allocation."""

    def __init__(self, sector: Sector, count: int, total: int, parent=None):
        super().__init__(parent)
        self.sector = sector
        self.count = count
        self.total = total
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        name = QLabel(self.sector.value)
        name.setFont(QFont("SF Pro Text", 12))
        name.setStyleSheet(f"color: {COLORS['text']};")
        name.setFixedWidth(140)
        layout.addWidget(name)

        pct = (self.count / self.total * 100) if self.total > 0 else 0
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(pct))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        color = SECTOR_COLORS.get(self.sector, COLORS['accent'])
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['bg_secondary']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(bar, 1)

        count_label = QLabel(f"{self.count}")
        count_label.setFont(QFont("SF Pro Text", 12, QFont.Weight.DemiBold))
        count_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        count_label.setFixedWidth(24)
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(count_label)


class MoverCard(QFrame):
    """A card showing a top mover stock."""

    def __init__(self, ticker: str, name: str, change_pct: float, price: float, parent=None):
        super().__init__(parent)
        self._setup_ui(ticker, name, change_pct, price)

    def _setup_ui(self, ticker: str, name: str, change_pct: float, price: float):
        is_positive = change_pct >= 0
        bg_color = COLORS['positive_bg'] if is_positive else COLORS['negative_bg']
        accent_color = COLORS['positive'] if is_positive else COLORS['negative']

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)

        ticker_label = QLabel(ticker)
        ticker_label.setFont(QFont("SF Pro Text", 13, QFont.Weight.Bold))
        ticker_label.setStyleSheet(f"color: {COLORS['text']};")
        left.addWidget(ticker_label)

        name_label = QLabel(name[:18] + "..." if len(name) > 18 else name)
        name_label.setFont(QFont("SF Pro Text", 11))
        name_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        left.addWidget(name_label)

        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        sign = "+" if change_pct >= 0 else ""
        change_label = QLabel(f"{sign}{change_pct:.1f}%")
        change_label.setFont(QFont("SF Pro Text", 14, QFont.Weight.Bold))
        change_label.setStyleSheet(f"color: {accent_color};")
        change_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(change_label)

        price_label = QLabel(f"${price:.2f}")
        price_label.setFont(QFont("SF Pro Text", 11))
        price_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(price_label)

        layout.addLayout(right)


class CredentialsDialog(QDialog):
    """Dialog for entering Alpaca API credentials."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alpaca Credentials")
        self.setFixedWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Connect to Alpaca")
        title.setFont(QFont("SF Pro Display", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(title)

        desc = QLabel("Enter your Alpaca API credentials to connect your account.")
        desc.setFont(QFont("SF Pro Text", 12))
        desc.setStyleSheet(f"color: {COLORS['text_secondary']};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("PKXXXXXXXXXXXXXXXX")
        self.api_key_input.setStyleSheet(self._input_style())
        form.addRow("API Key", self.api_key_input)

        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Enter your secret key")
        self.secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_key_input.setStyleSheet(self._input_style())
        form.addRow("Secret Key", self.secret_key_input)

        self.paper_checkbox = QCheckBox("Paper Trading (recommended for testing)")
        self.paper_checkbox.setChecked(True)
        self.paper_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_secondary']};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLORS['border']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
        """)
        form.addRow("", self.paper_checkbox)

        layout.addLayout(form)

        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['accent_light']};
                border: 1px solid {COLORS['accent']};
                border-radius: 8px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(14, 12, 14, 12)

        info_text = QLabel("Get your API keys from the Alpaca dashboard at alpaca.markets")
        info_text.setFont(QFont("SF Pro Text", 11))
        info_text.setStyleSheet(f"color: {COLORS['accent']};")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_frame)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        connect_btn = QPushButton("Connect")
        connect_btn.setFixedHeight(38)
        connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        connect_btn.clicked.connect(self._validate_and_accept)
        buttons.addWidget(connect_btn)

        layout.addLayout(buttons)

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {COLORS['text']};
                background: {COLORS['bg']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """

    def _validate_and_accept(self):
        api_key = self.api_key_input.text().strip()
        secret_key = self.secret_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your Alpaca API key.")
            return

        if not secret_key:
            QMessageBox.warning(self, "Missing Secret Key", "Please enter your Alpaca secret key.")
            return

        self.accept()

    def get_credentials(self) -> tuple[str, str, bool]:
        """Returns (api_key, secret_key, paper)."""
        return (
            self.api_key_input.text().strip(),
            self.secret_key_input.text().strip(),
            self.paper_checkbox.isChecked(),
        )


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


class DashboardPage(QWidget):
    """Dashboard page showing portfolio overview."""

    def __init__(self, watchlist: Watchlist, parent=None):
        super().__init__(parent)
        self.watchlist = watchlist
        self.prices: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(20)

        # Stats row - simple inline stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(32)

        self.total_label = self._create_stat("Stocks", str(len(self.watchlist.stocks)))
        stats_row.addLayout(self.total_label)

        self.gainers_label = self._create_stat("Gainers", "--", COLORS['positive'])
        stats_row.addLayout(self.gainers_label)

        self.losers_label = self._create_stat("Losers", "--", COLORS['negative'])
        stats_row.addLayout(self.losers_label)

        self.avg_label = self._create_stat("Avg Change", "--")
        stats_row.addLayout(self.avg_label)

        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Main content - two columns without heavy boxing
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)

        # Left column - Sector breakdown
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        sector_title = QLabel("Sector Breakdown")
        sector_title.setFont(QFont("SF Pro Text", 13, QFont.Weight.DemiBold))
        sector_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        left_col.addWidget(sector_title)

        self.sector_container = QVBoxLayout()
        self.sector_container.setSpacing(6)
        self._build_sector_bars()
        left_col.addLayout(self.sector_container)

        left_col.addStretch()
        content_layout.addLayout(left_col, 1)

        # Right column - Top movers
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        gainers_title = QLabel("Top Gainers")
        gainers_title.setFont(QFont("SF Pro Text", 13, QFont.Weight.DemiBold))
        gainers_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        right_col.addWidget(gainers_title)

        self.gainers_container = QVBoxLayout()
        self.gainers_container.setSpacing(6)
        right_col.addLayout(self.gainers_container)

        right_col.addSpacing(16)

        losers_title = QLabel("Top Losers")
        losers_title.setFont(QFont("SF Pro Text", 13, QFont.Weight.DemiBold))
        losers_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        right_col.addWidget(losers_title)

        self.losers_container = QVBoxLayout()
        self.losers_container.setSpacing(6)
        right_col.addLayout(self.losers_container)

        right_col.addStretch()
        content_layout.addLayout(right_col, 1)

        layout.addLayout(content_layout, 1)

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
        value_widget.setObjectName(f"stat_{label.lower().replace(' ', '_')}")
        stat_layout.addWidget(value_widget)

        return stat_layout

    def _build_sector_bars(self):
        while self.sector_container.count():
            item = self.sector_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sector_counts = {}
        for stock in self.watchlist.stocks:
            sector_counts[stock.sector] = sector_counts.get(stock.sector, 0) + 1

        total = len(self.watchlist.stocks)
        sorted_sectors = sorted(sector_counts.items(), key=lambda x: -x[1])

        for sector, count in sorted_sectors:
            bar = SectorBar(sector, count, total)
            self.sector_container.addWidget(bar)

    def update_prices(self, prices: dict):
        self.prices = prices
        self._update_stats()
        self._update_movers()

    def _update_stats(self):
        if not self.prices:
            return

        gainers = 0
        losers = 0
        total_change = 0
        count = 0

        for ticker, data in self.prices.items():
            change = data.get("change_pct", 0)
            if change >= 0:
                gainers += 1
            else:
                losers += 1
            total_change += change
            count += 1

        # Update stats using findChild
        total_widget = self.findChild(QLabel, "stat_stocks")
        if total_widget:
            total_widget.setText(str(len(self.watchlist.stocks)))

        gainers_widget = self.findChild(QLabel, "stat_gainers")
        if gainers_widget:
            gainers_widget.setText(str(gainers))

        losers_widget = self.findChild(QLabel, "stat_losers")
        if losers_widget:
            losers_widget.setText(str(losers))

        avg_widget = self.findChild(QLabel, "stat_avg_change")
        if avg_widget and count > 0:
            avg = total_change / count
            sign = "+" if avg >= 0 else ""
            color = COLORS['positive'] if avg >= 0 else COLORS['negative']
            avg_widget.setText(f"{sign}{avg:.2f}%")
            avg_widget.setStyleSheet(f"color: {color};")

    def _update_movers(self):
        while self.gainers_container.count():
            item = self.gainers_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        while self.losers_container.count():
            item = self.losers_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.prices:
            return

        stock_data = []
        for stock in self.watchlist.stocks:
            if stock.ticker in self.prices:
                data = self.prices[stock.ticker]
                stock_data.append({
                    "ticker": stock.ticker,
                    "name": stock.name,
                    "price": data.get("price", 0),
                    "change_pct": data.get("change_pct", 0),
                })

        sorted_data = sorted(stock_data, key=lambda x: x["change_pct"], reverse=True)

        for item in sorted_data[:4]:
            if item["change_pct"] >= 0:
                card = MoverCard(item["ticker"], item["name"], item["change_pct"], item["price"])
                self.gainers_container.addWidget(card)

        for item in reversed(sorted_data[-4:]):
            if item["change_pct"] < 0:
                card = MoverCard(item["ticker"], item["name"], item["change_pct"], item["price"])
                self.losers_container.addWidget(card)

    def refresh(self):
        self._build_sector_bars()
        self._update_stats()
        self._update_movers()


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

        # Stats row - simple inline stats like dashboard
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

        self.positions_container = QVBoxLayout()
        self.positions_container.setSpacing(8)

        # Initial placeholder message
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
            self.broker = AlpacaBroker(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
            self._update_connected_state()
            self._refresh_account()
        except Exception as e:
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
        if not self.broker:
            return

        try:
            self.account_info = self.broker.get_account()
            self.positions = self.broker.get_positions()
            self._update_display()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch account data:\n{str(e)}")

    def _update_display(self):
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


class AddStockDialog(QDialog):
    """Dialog for adding a new stock to the watchlist."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock")
        self.setFixedWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Add to Watchlist")
        title.setFont(QFont("SF Pro Display", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("e.g. AAPL")
        self.ticker_input.setStyleSheet(self._input_style())
        form.addRow("Ticker", self.ticker_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Apple Inc.")
        self.name_input.setStyleSheet(self._input_style())
        form.addRow("Name", self.name_input)

        self.sector_combo = QComboBox()
        for sector in Sector:
            self.sector_combo.addItem(sector.value, sector)
        self.sector_combo.setStyleSheet(self._combo_style())
        form.addRow("Sector", self.sector_combo)

        self.risk_combo = QComboBox()
        for risk in RiskLevel:
            self.risk_combo.addItem(risk.value, risk)
        self.risk_combo.setCurrentIndex(1)
        self.risk_combo.setStyleSheet(self._combo_style())
        form.addRow("Risk", self.risk_combo)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        add_btn = QPushButton("Add Stock")
        add_btn.setFixedHeight(38)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        add_btn.clicked.connect(self._validate_and_accept)
        buttons.addWidget(add_btn)

        layout.addLayout(buttons)

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {COLORS['text']};
                background: {COLORS['bg']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {COLORS['text']};
                background: {COLORS['bg']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
        """

    def _validate_and_accept(self):
        ticker = self.ticker_input.text().strip().upper()
        name = self.name_input.text().strip()

        if not ticker:
            QMessageBox.warning(self, "Missing Ticker", "Please enter a ticker symbol.")
            return

        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a company name.")
            return

        self.accept()

    def get_stock(self) -> WatchlistStock:
        return WatchlistStock(
            ticker=self.ticker_input.text().strip().upper(),
            name=self.name_input.text().strip(),
            sector=self.sector_combo.currentData(),
            risk_level=self.risk_combo.currentData(),
            thesis="Added via GUI",
        )


class WatchlistPage(QWidget):
    """Watchlist table page."""

    stock_added = Signal()
    stock_removed = Signal()

    def __init__(self, watchlist: Watchlist, parent=None):
        super().__init__(parent)
        self.watchlist = watchlist
        self.prices: dict = {}
        self.filter_sector: Optional[Sector] = None
        self.filter_risk: Optional[RiskLevel] = None
        self.search_text = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(16)

        # Filter row
        filters = QHBoxLayout()
        filters.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(180)
        self.search_input.setStyleSheet(self._input_style())
        self.search_input.textChanged.connect(self._on_filter_changed)
        filters.addWidget(self.search_input)

        self.sector_combo = QComboBox()
        self.sector_combo.addItem("All Sectors", None)
        for sector in Sector:
            self.sector_combo.addItem(sector.value, sector)
        self.sector_combo.setFixedWidth(180)
        self.sector_combo.setStyleSheet(self._combo_style())
        self.sector_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters.addWidget(self.sector_combo)

        self.risk_combo = QComboBox()
        self.risk_combo.addItem("All Risk", None)
        for risk in RiskLevel:
            self.risk_combo.addItem(risk.value, risk)
        self.risk_combo.setFixedWidth(140)
        self.risk_combo.setStyleSheet(self._combo_style())
        self.risk_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters.addWidget(self.risk_combo)

        filters.addStretch()

        self.add_btn = QPushButton("+ Add Stock")
        self.add_btn.setFixedHeight(36)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        self.add_btn.clicked.connect(self._on_add_stock)
        filters.addWidget(self.add_btn)

        layout.addLayout(filters)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Ticker", "Name", "Price", "Change", "Sector", ""])
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                background-color: {COLORS['bg']};
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 10px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['accent_light']};
                color: {COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg']};
                color: {COLORS['text_muted']};
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                padding: 14px 10px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 4px;
            }}
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 160)
        self.table.setColumnWidth(5, 70)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setMouseTracking(True)

        layout.addWidget(self.table)

        self._populate_table()

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {COLORS['text']};
                background: {COLORS['bg']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {COLORS['text']};
                background: {COLORS['bg']};
            }}
            QComboBox:hover {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['bg']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['accent_light']};
            }}
        """

    def _get_filtered_stocks(self) -> list[WatchlistStock]:
        stocks = []
        for stock in self.watchlist.stocks:
            if self.filter_sector and stock.sector != self.filter_sector:
                continue
            if self.filter_risk and stock.risk_level != self.filter_risk:
                continue
            if self.search_text and self.search_text.upper() not in stock.ticker.upper():
                continue
            stocks.append(stock)
        return stocks

    def _populate_table(self):
        # Temporarily disable sorting while populating
        self.table.setSortingEnabled(False)

        stocks = self._get_filtered_stocks()
        self.table.setRowCount(len(stocks))

        for row, stock in enumerate(stocks):
            ticker_item = QTableWidgetItem(stock.ticker)
            ticker_item.setFont(QFont("SF Pro Text", 13, QFont.Weight.Bold))
            ticker_item.setForeground(QColor(COLORS['text']))
            ticker_item.setData(Qt.ItemDataRole.UserRole, stock.ticker)  # Store for sorting
            # Add thesis as tooltip
            if stock.thesis:
                ticker_item.setToolTip(f"Thesis: {stock.thesis}")
            self.table.setItem(row, 0, ticker_item)

            name_item = QTableWidgetItem(stock.name)
            name_item.setForeground(QColor(COLORS['text_secondary']))
            if stock.thesis:
                name_item.setToolTip(f"Thesis: {stock.thesis}")
            self.table.setItem(row, 1, name_item)

            price_item = QTableWidgetItem("--")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setForeground(QColor(COLORS['text']))
            price_item.setData(Qt.ItemDataRole.UserRole, 0.0)  # Store numeric value for sorting
            self.table.setItem(row, 2, price_item)

            change_item = QTableWidgetItem("--")
            change_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            change_item.setForeground(QColor(COLORS['text_muted']))
            change_item.setData(Qt.ItemDataRole.UserRole, 0.0)  # Store numeric value for sorting
            self.table.setItem(row, 3, change_item)

            sector_item = QTableWidgetItem(stock.sector.value)
            sector_item.setForeground(QColor(COLORS['text_muted']))
            self.table.setItem(row, 4, sector_item)

            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet(theme.button_ghost())
            remove_btn.clicked.connect(lambda checked, t=stock.ticker: self._on_remove_stock(t))
            self.table.setCellWidget(row, 5, remove_btn)

            self.table.setRowHeight(row, Dimensions.TABLE_ROW_HEIGHT)

        # Re-enable sorting after populating
        self.table.setSortingEnabled(True)

    def update_prices(self, prices: dict):
        self.prices = prices
        self._update_price_display()

    def _update_price_display(self):
        stocks = self._get_filtered_stocks()

        for row, stock in enumerate(stocks):
            if stock.ticker in self.prices:
                data = self.prices[stock.ticker]
                price = data.get("price", 0)
                change_pct = data.get("change_pct", 0)

                price_item = self.table.item(row, 2)
                if price_item:
                    price_item.setText(f"${price:.2f}")

                change_item = self.table.item(row, 3)
                if change_item:
                    sign = "+" if change_pct >= 0 else ""
                    change_item.setText(f"{sign}{change_pct:.1f}%")
                    color = COLORS['positive'] if change_pct >= 0 else COLORS['negative']
                    change_item.setForeground(QColor(color))

    def _on_filter_changed(self):
        self.filter_sector = self.sector_combo.currentData()
        self.filter_risk = self.risk_combo.currentData()
        self.search_text = self.search_input.text().strip()
        self._populate_table()
        self._update_price_display()

    def _on_add_stock(self):
        dialog = AddStockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stock = dialog.get_stock()

            if any(s.ticker == stock.ticker for s in self.watchlist.stocks):
                QMessageBox.warning(self, "Duplicate", f"{stock.ticker} is already in the watchlist.")
                return

            self.watchlist.stocks.append(stock)
            self._populate_table()
            self.stock_added.emit()

    def _on_remove_stock(self, ticker: str):
        # Confirm before removing
        reply = QMessageBox.question(
            self,
            "Remove Stock",
            f"Remove {ticker} from watchlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        logger.info(f"Removing {ticker} from watchlist")
        self.watchlist.stocks = [s for s in self.watchlist.stocks if s.ticker != ticker]
        if ticker in self.prices:
            del self.prices[ticker]
        self._populate_table()
        self._update_price_display()
        self.stock_removed.emit()


class WatchlistMonitor(QMainWindow):
    """Main watchlist monitoring window."""

    def __init__(self):
        super().__init__()
        self.watchlist = Watchlist()
        self.prices: dict = {}
        self.auto_refresh = True
        self.refresh_interval = 30
        self.price_worker: Optional[PriceWorker] = None
        self.executor = ThreadPoolExecutor(max_workers=1)

        self._setup_ui()
        self._setup_shortcuts()
        self._setup_timer()
        QTimer.singleShot(100, self.refresh_prices)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Ctrl+R to refresh prices
        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut.activated.connect(self.refresh_prices)

        # Ctrl+N to add new stock
        add_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        add_shortcut.activated.connect(self._show_add_stock_dialog)

        # Ctrl+1/2/3 to switch tabs
        tab1_shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        tab1_shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(0))

        tab2_shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        tab2_shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(1))

        tab3_shortcut = QShortcut(QKeySequence("Ctrl+3"), self)
        tab3_shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(2))

        # Ctrl+F to focus search
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._focus_search)

        logger.info("Keyboard shortcuts initialized")

    def _show_add_stock_dialog(self):
        """Show add stock dialog from shortcut."""
        self.tabs.setCurrentIndex(1)  # Switch to watchlist tab
        self.watchlist_page._on_add_stock()

    def _focus_search(self):
        """Focus the search input from shortcut."""
        self.tabs.setCurrentIndex(1)  # Switch to watchlist tab
        self.watchlist_page.search_input.setFocus()

    def _setup_ui(self):
        self.setWindowTitle("Qwen - Watchlist Monitor")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(f"background-color: {COLORS['bg_secondary']};")

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 0, 28, 0)

        title = QLabel("Qwen")
        title.setFont(QFont("SF Pro Display", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text']};")
        header_layout.addWidget(title)

        header_layout.addSpacing(32)
        header_layout.addStretch()

        self.status_label = QLabel("Loading...")
        self.status_label.setFont(QFont("SF Pro Text", 12))
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        header_layout.addWidget(self.status_label)

        header_layout.addSpacing(16)

        self.auto_checkbox = QCheckBox("Auto-refresh")
        self.auto_checkbox.setChecked(True)
        self.auto_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_secondary']};
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {COLORS['border']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.auto_checkbox.toggled.connect(self._on_auto_refresh_toggled)
        header_layout.addWidget(self.auto_checkbox)

        header_layout.addSpacing(12)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
            }}
        """)
        self.refresh_btn.clicked.connect(self.refresh_prices)
        header_layout.addWidget(self.refresh_btn)

        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {COLORS['bg_secondary']};
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                padding: 14px 24px;
                border: none;
                font-size: 13px;
                font-weight: 500;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                color: {COLORS['accent']};
                border-bottom: 2px solid {COLORS['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                color: {COLORS['text']};
            }}
        """)

        # Dashboard page
        self.dashboard_page = DashboardPage(self.watchlist)
        self.tabs.addTab(self.dashboard_page, "Dashboard")

        # Watchlist page
        self.watchlist_page = WatchlistPage(self.watchlist)
        self.watchlist_page.stock_added.connect(self._on_stock_changed)
        self.watchlist_page.stock_removed.connect(self._on_stock_changed)
        self.tabs.addTab(self.watchlist_page, "Watchlist")

        # Account page
        self.account_page = AccountPage()
        self.tabs.addTab(self.account_page, "Account")

        layout.addWidget(self.tabs)

    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_prices)
        if self.auto_refresh:
            self.timer.start(self.refresh_interval * 1000)

    def refresh_prices(self):
        if not YFINANCE_AVAILABLE:
            self.status_label.setText("yfinance not installed")
            return

        self.status_label.setText("Updating...")
        self.refresh_btn.setEnabled(False)

        tickers = self.watchlist.tickers
        if not tickers:
            self.status_label.setText("No stocks in watchlist")
            self.refresh_btn.setEnabled(True)
            return

        self.price_worker = PriceWorker(tickers)
        # Use QueuedConnection for thread safety when signals come from worker thread
        self.price_worker.prices_ready.connect(
            self._on_prices_ready,
            Qt.ConnectionType.QueuedConnection
        )
        self.price_worker.error.connect(
            self._on_price_error,
            Qt.ConnectionType.QueuedConnection
        )
        self.executor.submit(self.price_worker.fetch_prices)

    def _on_prices_ready(self, prices: dict):
        self.prices = prices

        self.dashboard_page.update_prices(prices)
        self.watchlist_page.update_prices(prices)

        now = datetime.now().strftime("%H:%M")
        self.status_label.setText(f"{len(self.watchlist.stocks)} stocks · {now}")
        self.refresh_btn.setEnabled(True)

    def _on_price_error(self, error: str):
        self.status_label.setText(f"Error: {error}")
        self.refresh_btn.setEnabled(True)

    def _on_auto_refresh_toggled(self, checked: bool):
        self.auto_refresh = checked
        if checked:
            self.timer.start(self.refresh_interval * 1000)
        else:
            self.timer.stop()

    def _on_stock_changed(self):
        self.dashboard_page.refresh()
        self.refresh_prices()

    def closeEvent(self, event):
        if self.price_worker:
            self.price_worker.stop()
        self.executor.shutdown(wait=False)
        event.accept()


def run_monitor():
    """Launch the watchlist monitor application."""
    app = QApplication(sys.argv)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['bg']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS['text']))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS['bg']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS['bg_secondary']))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS['text']))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS['bg']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS['text']))
    app.setPalette(palette)

    font = QFont("SF Pro Text", 13)
    app.setFont(font)

    window = WatchlistMonitor()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_monitor()
