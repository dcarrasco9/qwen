"""Dashboard page showing portfolio overview and market summary."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from qwen.watchlist import Watchlist, Sector
from qwen.gui.theme import COLORS, SECTOR_COLORS


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


class DashboardPage(QWidget):
    """Dashboard page showing portfolio overview and market summary."""

    def __init__(self, watchlist: Watchlist, parent=None):
        """
        Initialize dashboard page.

        Args:
            watchlist: Watchlist instance with stocks to display
            parent: Parent widget
        """
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
        """Build sector breakdown bars."""
        # Clear existing
        while self.sector_container.count():
            item = self.sector_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Count stocks by sector
        sector_counts = {}
        for stock in self.watchlist.stocks:
            sector_counts[stock.sector] = sector_counts.get(stock.sector, 0) + 1

        total = len(self.watchlist.stocks)
        sorted_sectors = sorted(sector_counts.items(), key=lambda x: -x[1])

        for sector, count in sorted_sectors:
            bar = SectorBar(sector, count, total)
            self.sector_container.addWidget(bar)

    def update_prices(self, prices: dict):
        """Update dashboard with new price data."""
        self.prices = prices
        self._update_stats()
        self._update_movers()

    def _update_stats(self):
        """Update stat cards with current data."""
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
        """Update top gainers and losers."""
        # Clear existing
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

        # Build stock data list
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

        # Top gainers
        for item in sorted_data[:4]:
            if item["change_pct"] >= 0:
                card = MoverCard(item["ticker"], item["name"], item["change_pct"], item["price"])
                self.gainers_container.addWidget(card)

        # Top losers
        for item in reversed(sorted_data[-4:]):
            if item["change_pct"] < 0:
                card = MoverCard(item["ticker"], item["name"], item["change_pct"], item["price"])
                self.losers_container.addWidget(card)

    def refresh(self):
        """Refresh all dashboard content."""
        self._build_sector_bars()
        self._update_stats()
        self._update_movers()
