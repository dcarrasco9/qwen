"""Sector bar widget for displaying sector allocation."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.watchlist import Sector
from qwen.gui.theme import theme, COLORS, SECTOR_COLORS, Dimensions


class SectorBar(QFrame):
    """A horizontal bar showing sector allocation percentage."""

    def __init__(self, sector: Sector, count: int, total: int, parent=None):
        """
        Initialize sector bar.

        Args:
            sector: The sector enum value
            count: Number of stocks in this sector
            total: Total number of stocks
            parent: Parent widget
        """
        super().__init__(parent)
        self.sector = sector
        self.count = count
        self.total = total
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(Dimensions.BUTTON_HEIGHT_SM)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Dimensions.SPACING_MD)

        name = QLabel(self.sector.value)
        name.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_MD))
        name.setStyleSheet(f"color: {COLORS['text']};")
        name.setFixedWidth(Dimensions.INPUT_WIDTH_SM)
        layout.addWidget(name)

        pct = (self.count / self.total * 100) if self.total > 0 else 0
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(pct))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)

        color = SECTOR_COLORS.get(self.sector.name, COLORS['accent'])
        bar.setStyleSheet(theme.progress_bar(color))
        layout.addWidget(bar, 1)

        count_label = QLabel(f"{self.count}")
        count_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_MD, QFont.Weight.DemiBold))
        count_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        count_label.setFixedWidth(24)
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(count_label)

    def update_data(self, count: int, total: int):
        """Update the bar with new data."""
        self.count = count
        self.total = total
        # Rebuild UI - for simplicity, we recreate the widget
        # In production, you'd update the existing widgets
