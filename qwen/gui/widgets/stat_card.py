"""Stat card widget for displaying key metrics."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtGui import QFont

from qwen.gui.theme import theme, COLORS, Dimensions


class StatCard(QFrame):
    """A clean stat card widget for displaying key metrics."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        """
        Initialize stat card.

        Args:
            title: Card title (displayed uppercase)
            value: Main value to display
            subtitle: Optional subtitle text
            parent: Parent widget
        """
        super().__init__(parent)
        self._setup_ui(title, value, subtitle)

    def _setup_ui(self, title: str, value: str, subtitle: str):
        self.setStyleSheet(theme.card_frame())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Dimensions.MARGIN_CARD,
            Dimensions.MARGIN_CARD - 2,
            Dimensions.MARGIN_CARD,
            Dimensions.MARGIN_CARD - 2
        )
        layout.setSpacing(6)

        self.title_label = QLabel(title.upper())
        self.title_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_XS, QFont.Weight.Medium))
        self.title_label.setStyleSheet(f"color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("SF Pro Display", Dimensions.FONT_SIZE_STAT, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(self.value_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_SM))
            self.subtitle_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

    def set_value(self, value: str, color: str = None):
        """Update the displayed value."""
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        else:
            self.value_label.setStyleSheet(f"color: {COLORS['text']};")

    def set_subtitle(self, text: str):
        """Update the subtitle text."""
        if self.subtitle_label:
            self.subtitle_label.setText(text)
