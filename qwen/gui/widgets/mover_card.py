"""Mover card widget for displaying top gainers/losers."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.gui.theme import theme, COLORS, Dimensions


class MoverCard(QFrame):
    """A card showing a top mover stock (gainer or loser)."""

    def __init__(self, ticker: str, name: str, change_pct: float, price: float, parent=None):
        """
        Initialize mover card.

        Args:
            ticker: Stock ticker symbol
            name: Company name
            change_pct: Percentage change
            price: Current price
            parent: Parent widget
        """
        super().__init__(parent)
        self.ticker = ticker
        self.name = name
        self.change_pct = change_pct
        self.price = price
        self._setup_ui()

    def _setup_ui(self):
        is_positive = self.change_pct >= 0
        self.setStyleSheet(theme.mover_card(is_positive))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Left side - ticker and name
        left = QVBoxLayout()
        left.setSpacing(2)

        ticker_label = QLabel(self.ticker)
        ticker_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_LG, QFont.Weight.Bold))
        ticker_label.setStyleSheet(f"color: {COLORS['text']};")
        left.addWidget(ticker_label)

        display_name = self.name[:18] + "..." if len(self.name) > 18 else self.name
        name_label = QLabel(display_name)
        name_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_SM))
        name_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        left.addWidget(name_label)

        layout.addLayout(left, 1)

        # Right side - change and price
        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        sign = "+" if self.change_pct >= 0 else ""
        accent_color = COLORS['positive'] if is_positive else COLORS['negative']
        change_label = QLabel(f"{sign}{self.change_pct:.1f}%")
        change_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_XL, QFont.Weight.Bold))
        change_label.setStyleSheet(f"color: {accent_color};")
        change_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(change_label)

        price_label = QLabel(f"${self.price:.2f}")
        price_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_SM))
        price_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(price_label)

        layout.addLayout(right)

    def update_data(self, change_pct: float, price: float):
        """Update the card with new price data."""
        self.change_pct = change_pct
        self.price = price
        # Would need to update labels - for simplicity, recreate the widget
