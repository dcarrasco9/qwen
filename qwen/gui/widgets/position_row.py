"""Position row widget for displaying portfolio positions."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.gui.theme import theme, COLORS, Dimensions


class PositionRow(QFrame):
    """A row showing a portfolio position with P&L details."""

    def __init__(
        self,
        symbol: str,
        qty: float,
        avg_price: float,
        current_price: float,
        unrealized_pl: float,
        unrealized_plpc: float,
        parent=None
    ):
        """
        Initialize position row.

        Args:
            symbol: Stock ticker symbol
            qty: Number of shares
            avg_price: Average entry price
            current_price: Current market price
            unrealized_pl: Unrealized profit/loss in dollars
            unrealized_plpc: Unrealized profit/loss percentage
            parent: Parent widget
        """
        super().__init__(parent)
        self._setup_ui(symbol, qty, avg_price, current_price, unrealized_pl, unrealized_plpc)

    def _setup_ui(
        self,
        symbol: str,
        qty: float,
        avg_price: float,
        current_price: float,
        unrealized_pl: float,
        unrealized_plpc: float
    ):
        is_positive = unrealized_pl >= 0
        self.setStyleSheet(theme.card_frame_hover())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(Dimensions.SPACING_LG)

        # Symbol and quantity
        left = QVBoxLayout()
        left.setSpacing(2)

        symbol_label = QLabel(symbol)
        symbol_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_XL, QFont.Weight.Bold))
        symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        left.addWidget(symbol_label)

        qty_label = QLabel(f"{qty:.2f} shares")
        qty_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_SM))
        qty_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        left.addWidget(qty_label)

        layout.addLayout(left)
        layout.addStretch()

        # Average cost
        self._add_metric_column(layout, "Avg Cost", f"${avg_price:.2f}")

        # Current price
        self._add_metric_column(layout, "Current", f"${current_price:.2f}")

        # Market value
        market_value = qty * current_price
        self._add_metric_column(layout, "Value", f"${market_value:,.2f}", bold=True)

        # P&L
        color = COLORS['positive'] if is_positive else COLORS['negative']
        sign = "+" if is_positive else ""
        pl_text = f"{sign}${unrealized_pl:,.2f} ({sign}{unrealized_plpc*100:.1f}%)"
        self._add_metric_column(layout, "P&L", pl_text, color=color, bold=True)

    def _add_metric_column(
        self,
        parent_layout: QHBoxLayout,
        title: str,
        value: str,
        color: str = None,
        bold: bool = False
    ):
        """Add a metric column to the layout."""
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setAlignment(Qt.AlignmentFlag.AlignRight)

        title_label = QLabel(title)
        title_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_XS))
        title_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        col.addWidget(title_label)

        weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
        value_label = QLabel(value)
        value_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_MD, weight))
        value_label.setStyleSheet(f"color: {color or COLORS['text']};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        col.addWidget(value_label)

        parent_layout.addLayout(col)
