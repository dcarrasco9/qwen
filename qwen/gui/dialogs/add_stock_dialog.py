"""Dialog for adding a new stock to the watchlist."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QFormLayout,
    QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.watchlist import WatchlistStock, Sector, RiskLevel
from qwen.gui.theme import theme, COLORS, Dimensions


class AddStockDialog(QDialog):
    """Dialog for adding a new stock to the watchlist."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock")
        self.setFixedWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(Dimensions.SPACING_XL)
        layout.setContentsMargins(
            Dimensions.SPACING_XXL,
            Dimensions.SPACING_XXL,
            Dimensions.SPACING_XXL,
            Dimensions.SPACING_XXL
        )

        # Title
        title = QLabel("Add to Watchlist")
        title.setFont(QFont("SF Pro Display", Dimensions.FONT_SIZE_TITLE, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("e.g. AAPL")
        self.ticker_input.setStyleSheet(theme.input_style())
        form.addRow("Ticker", self.ticker_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Apple Inc.")
        self.name_input.setStyleSheet(theme.input_style())
        form.addRow("Name", self.name_input)

        self.thesis_input = QLineEdit()
        self.thesis_input.setPlaceholderText("e.g. Strong AI play with services growth")
        self.thesis_input.setStyleSheet(theme.input_style())
        form.addRow("Thesis", self.thesis_input)

        self.sector_combo = QComboBox()
        for sector in Sector:
            self.sector_combo.addItem(sector.value, sector)
        self.sector_combo.setStyleSheet(theme.combo_style())
        form.addRow("Sector", self.sector_combo)

        self.risk_combo = QComboBox()
        for risk in RiskLevel:
            self.risk_combo.addItem(risk.value, risk)
        self.risk_combo.setCurrentIndex(1)  # Default to medium risk
        self.risk_combo.setStyleSheet(theme.combo_style())
        form.addRow("Risk", self.risk_combo)

        layout.addLayout(form)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(Dimensions.SPACING_MD)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_MD)
        cancel_btn.setStyleSheet(theme.button_secondary())
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        add_btn = QPushButton("Add Stock")
        add_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_MD)
        add_btn.setStyleSheet(theme.button_primary())
        add_btn.clicked.connect(self._validate_and_accept)
        buttons.addWidget(add_btn)

        layout.addLayout(buttons)

    def _validate_and_accept(self):
        """Validate inputs and accept dialog."""
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
        """Get the stock from dialog inputs.

        Returns:
            WatchlistStock with entered values
        """
        thesis = self.thesis_input.text().strip() or "Added via GUI"
        return WatchlistStock(
            ticker=self.ticker_input.text().strip().upper(),
            name=self.name_input.text().strip(),
            sector=self.sector_combo.currentData(),
            risk_level=self.risk_combo.currentData(),
            thesis=thesis,
        )
