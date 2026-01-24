"""Watchlist page with stock table and filters."""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from qwen.watchlist import Watchlist, WatchlistStock, Sector, RiskLevel
from qwen.gui.theme import theme, COLORS, Dimensions
from qwen.gui.dialogs import AddStockDialog

logger = logging.getLogger(__name__)


class WatchlistPage(QWidget):
    """Watchlist table page with filtering and sorting."""

    stock_added = Signal()
    stock_removed = Signal()

    def __init__(self, watchlist: Watchlist, parent=None):
        """
        Initialize watchlist page.

        Args:
            watchlist: Watchlist instance to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.watchlist = watchlist
        self.prices: dict = {}
        self.filter_sector: Optional[Sector] = None
        self.filter_risk: Optional[RiskLevel] = None
        self.search_text = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Dimensions.MARGIN_PAGE,
            Dimensions.SPACING_XXL,
            Dimensions.MARGIN_PAGE,
            Dimensions.SPACING_LG
        )
        layout.setSpacing(Dimensions.SPACING_LG)

        # Filter row
        filters = QHBoxLayout()
        filters.setSpacing(Dimensions.SPACING_MD)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(Dimensions.INPUT_WIDTH_MD)
        self.search_input.setStyleSheet(theme.input_style())
        self.search_input.textChanged.connect(self._on_filter_changed)
        filters.addWidget(self.search_input)

        self.sector_combo = QComboBox()
        self.sector_combo.addItem("All Sectors", None)
        for sector in Sector:
            self.sector_combo.addItem(sector.value, sector)
        self.sector_combo.setFixedWidth(Dimensions.INPUT_WIDTH_MD)
        self.sector_combo.setStyleSheet(theme.combo_style())
        self.sector_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters.addWidget(self.sector_combo)

        self.risk_combo = QComboBox()
        self.risk_combo.addItem("All Risk", None)
        for risk in RiskLevel:
            self.risk_combo.addItem(risk.value, risk)
        self.risk_combo.setFixedWidth(Dimensions.INPUT_WIDTH_SM)
        self.risk_combo.setStyleSheet(theme.combo_style())
        self.risk_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters.addWidget(self.risk_combo)

        filters.addStretch()

        self.add_btn = QPushButton("+ Add Stock")
        self.add_btn.setFixedHeight(36)
        self.add_btn.setStyleSheet(theme.button_primary())
        self.add_btn.clicked.connect(self._on_add_stock)
        filters.addWidget(self.add_btn)

        layout.addLayout(filters)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Ticker", "Name", "Price", "Change", "Sector", ""])
        self.table.setStyleSheet(theme.table_style())

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, Dimensions.TABLE_COL_TICKER)
        self.table.setColumnWidth(2, Dimensions.TABLE_COL_PRICE)
        self.table.setColumnWidth(3, Dimensions.TABLE_COL_CHANGE)
        self.table.setColumnWidth(4, Dimensions.TABLE_COL_SECTOR)
        self.table.setColumnWidth(5, Dimensions.TABLE_COL_ACTION)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setMouseTracking(True)

        layout.addWidget(self.table)

        self._populate_table()

    def _get_filtered_stocks(self) -> list[WatchlistStock]:
        """Get stocks matching current filters."""
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
        """Populate table with filtered stocks."""
        # Temporarily disable sorting while populating
        self.table.setSortingEnabled(False)

        stocks = self._get_filtered_stocks()
        self.table.setRowCount(len(stocks))

        for row, stock in enumerate(stocks):
            # Ticker
            ticker_item = QTableWidgetItem(stock.ticker)
            ticker_item.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_LG, QFont.Weight.Bold))
            ticker_item.setForeground(QColor(COLORS['text']))
            ticker_item.setData(Qt.ItemDataRole.UserRole, stock.ticker)
            if stock.thesis:
                ticker_item.setToolTip(f"Thesis: {stock.thesis}")
            self.table.setItem(row, 0, ticker_item)

            # Name
            name_item = QTableWidgetItem(stock.name)
            name_item.setForeground(QColor(COLORS['text_secondary']))
            if stock.thesis:
                name_item.setToolTip(f"Thesis: {stock.thesis}")
            self.table.setItem(row, 1, name_item)

            # Price
            price_item = QTableWidgetItem("--")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setForeground(QColor(COLORS['text']))
            price_item.setData(Qt.ItemDataRole.UserRole, 0.0)
            self.table.setItem(row, 2, price_item)

            # Change
            change_item = QTableWidgetItem("--")
            change_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            change_item.setForeground(QColor(COLORS['text_muted']))
            change_item.setData(Qt.ItemDataRole.UserRole, 0.0)
            self.table.setItem(row, 3, change_item)

            # Sector
            sector_item = QTableWidgetItem(stock.sector.value)
            sector_item.setForeground(QColor(COLORS['text_muted']))
            self.table.setItem(row, 4, sector_item)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet(theme.button_ghost())
            remove_btn.clicked.connect(lambda checked, t=stock.ticker: self._on_remove_stock(t))
            self.table.setCellWidget(row, 5, remove_btn)

            self.table.setRowHeight(row, Dimensions.TABLE_ROW_HEIGHT)

        # Re-enable sorting after populating
        self.table.setSortingEnabled(True)

    def update_prices(self, prices: dict):
        """Update table with new price data."""
        self.prices = prices
        self._update_price_display()

    def _update_price_display(self):
        """Update price and change columns."""
        stocks = self._get_filtered_stocks()

        for row, stock in enumerate(stocks):
            if stock.ticker in self.prices:
                data = self.prices[stock.ticker]
                price = data.get("price", 0)
                change_pct = data.get("change_pct", 0)

                price_item = self.table.item(row, 2)
                if price_item:
                    price_item.setText(f"${price:.2f}")
                    price_item.setData(Qt.ItemDataRole.UserRole, price)

                change_item = self.table.item(row, 3)
                if change_item:
                    sign = "+" if change_pct >= 0 else ""
                    change_item.setText(f"{sign}{change_pct:.1f}%")
                    change_item.setData(Qt.ItemDataRole.UserRole, change_pct)
                    color = COLORS['positive'] if change_pct >= 0 else COLORS['negative']
                    change_item.setForeground(QColor(color))

    def _on_filter_changed(self):
        """Handle filter changes."""
        self.filter_sector = self.sector_combo.currentData()
        self.filter_risk = self.risk_combo.currentData()
        self.search_text = self.search_input.text().strip()
        self._populate_table()
        self._update_price_display()

    def _on_add_stock(self):
        """Show add stock dialog."""
        dialog = AddStockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stock = dialog.get_stock()

            if any(s.ticker == stock.ticker for s in self.watchlist.stocks):
                QMessageBox.warning(self, "Duplicate", f"{stock.ticker} is already in the watchlist.")
                return

            logger.info(f"Adding {stock.ticker} to watchlist")
            self.watchlist.stocks.append(stock)
            self._populate_table()
            self.stock_added.emit()

    def _on_remove_stock(self, ticker: str):
        """Remove stock from watchlist with confirmation."""
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
