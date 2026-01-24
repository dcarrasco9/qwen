"""Dialog for entering Alpaca API credentials."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QFormLayout,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from qwen.gui.theme import theme, COLORS, Dimensions


class CredentialsDialog(QDialog):
    """Dialog for entering Alpaca API credentials."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alpaca Credentials")
        self.setFixedWidth(420)
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
        title = QLabel("Connect to Alpaca")
        title.setFont(QFont("SF Pro Display", Dimensions.FONT_SIZE_TITLE, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(title)

        # Description
        desc = QLabel("Enter your Alpaca API credentials to connect your account.")
        desc.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_MD))
        desc.setStyleSheet(f"color: {COLORS['text_secondary']};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Form
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("PKXXXXXXXXXXXXXXXX")
        self.api_key_input.setStyleSheet(theme.input_style())
        form.addRow("API Key", self.api_key_input)

        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Enter your secret key")
        self.secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_key_input.setStyleSheet(theme.input_style())
        form.addRow("Secret Key", self.secret_key_input)

        self.paper_checkbox = QCheckBox("Paper Trading (recommended for testing)")
        self.paper_checkbox.setChecked(True)
        self.paper_checkbox.setStyleSheet(theme.checkbox_style())
        form.addRow("", self.paper_checkbox)

        layout.addLayout(form)

        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet(theme.info_box())
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(14, 12, 14, 12)

        info_text = QLabel("Get your API keys from the Alpaca dashboard at alpaca.markets")
        info_text.setFont(QFont("SF Pro Text", Dimensions.FONT_SIZE_SM))
        info_text.setStyleSheet(f"color: {COLORS['accent']};")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_frame)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(Dimensions.SPACING_MD)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_MD)
        cancel_btn.setStyleSheet(theme.button_secondary())
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        connect_btn = QPushButton("Connect")
        connect_btn.setFixedHeight(Dimensions.BUTTON_HEIGHT_MD)
        connect_btn.setStyleSheet(theme.button_primary())
        connect_btn.clicked.connect(self._validate_and_accept)
        buttons.addWidget(connect_btn)

        layout.addLayout(buttons)

    def _validate_and_accept(self):
        """Validate inputs and accept dialog."""
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
        """Get the entered credentials.

        Returns:
            Tuple of (api_key, secret_key, paper_trading_enabled)
        """
        return (
            self.api_key_input.text().strip(),
            self.secret_key_input.text().strip(),
            self.paper_checkbox.isChecked(),
        )
