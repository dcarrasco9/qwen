"""
Qwen GUI Theme System

Centralized theming for consistent styling across all GUI components.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class Dimensions:
    """Standard dimensions for UI elements."""

    # Button heights
    BUTTON_HEIGHT_SM = 32
    BUTTON_HEIGHT_MD = 38
    BUTTON_HEIGHT_LG = 44

    # Input widths
    INPUT_WIDTH_SM = 140
    INPUT_WIDTH_MD = 180
    INPUT_WIDTH_LG = 240

    # Border radius
    RADIUS_SM = 6
    RADIUS_MD = 8
    RADIUS_LG = 10
    RADIUS_XL = 12

    # Spacing
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 20
    SPACING_XXL = 24

    # Margins
    MARGIN_PAGE = 28
    MARGIN_CARD = 20

    # Font sizes
    FONT_SIZE_XS = 10
    FONT_SIZE_SM = 11
    FONT_SIZE_MD = 12
    FONT_SIZE_LG = 13
    FONT_SIZE_XL = 14
    FONT_SIZE_XXL = 15
    FONT_SIZE_TITLE = 16
    FONT_SIZE_HEADER = 20
    FONT_SIZE_STAT = 28

    # Fixed widths
    TABLE_COL_TICKER = 80
    TABLE_COL_PRICE = 100
    TABLE_COL_CHANGE = 90
    TABLE_COL_SECTOR = 160
    TABLE_COL_ACTION = 70

    # Row heights
    TABLE_ROW_HEIGHT = 52
    HEADER_HEIGHT = 64
    STATUS_INDICATOR_SIZE = 8


# Light theme colors
COLORS_LIGHT: Dict[str, str] = {
    "bg": "#ffffff",
    "bg_secondary": "#f8fafc",
    "bg_hover": "#f1f5f9",
    "text": "#0f172a",
    "text_secondary": "#475569",
    "text_muted": "#94a3b8",
    "positive": "#10b981",
    "positive_bg": "#ecfdf5",
    "negative": "#ef4444",
    "negative_bg": "#fef2f2",
    "border": "#e2e8f0",
    "accent": "#3b82f6",
    "accent_light": "#eff6ff",
    "accent_hover": "#2563eb",
}

# Dark theme colors (for future use)
COLORS_DARK: Dict[str, str] = {
    "bg": "#0f172a",
    "bg_secondary": "#1e293b",
    "bg_hover": "#334155",
    "text": "#f8fafc",
    "text_secondary": "#cbd5e1",
    "text_muted": "#64748b",
    "positive": "#34d399",
    "positive_bg": "#064e3b",
    "negative": "#f87171",
    "negative_bg": "#7f1d1d",
    "border": "#334155",
    "accent": "#60a5fa",
    "accent_light": "#1e3a5f",
    "accent_hover": "#3b82f6",
}

# Sector colors
SECTOR_COLORS: Dict[str, str] = {
    "AI_SEMICONDUCTORS": "#8b5cf6",
    "DEFENSE": "#ef4444",
    "DATA_CENTER": "#3b82f6",
    "NUCLEAR": "#f59e0b",
    "EVTOL": "#10b981",
    "NETWORKING": "#06b6d4",
    "COOLING": "#6366f1",
    "HYPERSCALER": "#ec4899",
    "SPACE_SATELLITE": "#14b8a6",
}


class Theme:
    """Centralized theme with style generators."""

    def __init__(self, colors: Dict[str, str] = None):
        self.colors = colors or COLORS_LIGHT
        self.dim = Dimensions()

    def input_style(self) -> str:
        """Standard input field style."""
        return f"""
            QLineEdit {{
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_MD}px;
                padding: 10px 14px;
                font-size: {self.dim.FONT_SIZE_LG}px;
                color: {self.colors['text']};
                background: {self.colors['bg']};
            }}
            QLineEdit:focus {{
                border-color: {self.colors['accent']};
            }}
        """

    def combo_style(self) -> str:
        """Standard combobox style."""
        return f"""
            QComboBox {{
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_MD}px;
                padding: 10px 14px;
                font-size: {self.dim.FONT_SIZE_LG}px;
                color: {self.colors['text']};
                background: {self.colors['bg']};
            }}
            QComboBox:hover {{
                border-color: {self.colors['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.colors['bg']};
                border: 1px solid {self.colors['border']};
                selection-background-color: {self.colors['accent_light']};
            }}
        """

    def button_primary(self) -> str:
        """Primary action button style."""
        return f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                color: white;
                border: none;
                border-radius: {self.dim.RADIUS_MD}px;
                padding: 0 20px;
                font-size: {self.dim.FONT_SIZE_LG}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {self.colors['border']};
            }}
        """

    def button_secondary(self) -> str:
        """Secondary/outline button style."""
        return f"""
            QPushButton {{
                background-color: {self.colors['bg']};
                color: {self.colors['text']};
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_MD}px;
                padding: 0 20px;
                font-size: {self.dim.FONT_SIZE_LG}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_hover']};
            }}
        """

    def button_danger(self) -> str:
        """Danger/destructive action button style."""
        return f"""
            QPushButton {{
                background-color: {self.colors['bg']};
                color: {self.colors['negative']};
                border: 1px solid {self.colors['negative']};
                border-radius: {self.dim.RADIUS_SM}px;
                padding: 0 16px;
                font-size: {self.dim.FONT_SIZE_MD}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['negative_bg']};
            }}
        """

    def button_ghost(self) -> str:
        """Ghost/minimal button style."""
        return f"""
            QPushButton {{
                background: none;
                border: none;
                color: {self.colors['text_muted']};
                font-size: {self.dim.FONT_SIZE_SM}px;
                padding: 4px;
            }}
            QPushButton:hover {{
                color: {self.colors['negative']};
            }}
        """

    def button_refresh(self) -> str:
        """Refresh button style (connected state)."""
        return f"""
            QPushButton {{
                background-color: {self.colors['bg']};
                color: {self.colors['text']};
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_SM}px;
                padding: 0 16px;
                font-size: {self.dim.FONT_SIZE_MD}px;
            }}
            QPushButton:hover {{
                border-color: {self.colors['accent']};
                color: {self.colors['accent']};
            }}
        """

    def checkbox_style(self) -> str:
        """Standard checkbox style."""
        return f"""
            QCheckBox {{
                color: {self.colors['text_secondary']};
                font-size: {self.dim.FONT_SIZE_MD}px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {self.colors['border']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['accent']};
                border-color: {self.colors['accent']};
            }}
        """

    def card_frame(self) -> str:
        """Standard card/frame style."""
        return f"""
            QFrame {{
                background-color: {self.colors['bg']};
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_XL}px;
            }}
        """

    def card_frame_hover(self) -> str:
        """Card with hover effect."""
        return f"""
            QFrame {{
                background-color: {self.colors['bg']};
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_LG}px;
            }}
            QFrame:hover {{
                background-color: {self.colors['bg_hover']};
            }}
        """

    def info_box(self) -> str:
        """Information/help box style."""
        return f"""
            QFrame {{
                background-color: {self.colors['accent_light']};
                border: 1px solid {self.colors['accent']};
                border-radius: {self.dim.RADIUS_MD}px;
            }}
        """

    def table_style(self) -> str:
        """Standard table widget style."""
        return f"""
            QTableWidget {{
                border: 1px solid {self.colors['border']};
                border-radius: {self.dim.RADIUS_LG}px;
                background-color: {self.colors['bg']};
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 10px;
                border: none;
                border-bottom: 1px solid {self.colors['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {self.colors['accent_light']};
                color: {self.colors['text']};
            }}
            QHeaderView::section {{
                background-color: {self.colors['bg']};
                color: {self.colors['text_muted']};
                font-weight: 600;
                font-size: {self.dim.FONT_SIZE_SM}px;
                text-transform: uppercase;
                padding: 14px 10px;
                border: none;
                border-bottom: 1px solid {self.colors['border']};
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {self.colors['border']};
                border-radius: 4px;
            }}
        """

    def tab_style(self) -> str:
        """Tab widget style."""
        return f"""
            QTabWidget::pane {{
                border: none;
                background-color: {self.colors['bg_secondary']};
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {self.colors['text_muted']};
                padding: 14px 24px;
                border: none;
                font-size: {self.dim.FONT_SIZE_LG}px;
                font-weight: 500;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                color: {self.colors['accent']};
                border-bottom: 2px solid {self.colors['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                color: {self.colors['text']};
            }}
        """

    def header_style(self) -> str:
        """Main header bar style."""
        return f"""
            QFrame {{
                background-color: {self.colors['bg']};
                border-bottom: 1px solid {self.colors['border']};
            }}
        """

    def status_indicator(self, connected: bool = False) -> str:
        """Connection status indicator style."""
        color = self.colors['positive'] if connected else self.colors['text_muted']
        return f"""
            QFrame {{
                background-color: {color};
                border-radius: 4px;
            }}
        """

    def progress_bar(self, color: str) -> str:
        """Progress bar style with custom color."""
        return f"""
            QProgressBar {{
                background-color: {self.colors['bg_secondary']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """

    def mover_card(self, is_positive: bool) -> str:
        """Mover card style (gainer/loser)."""
        bg_color = self.colors['positive_bg'] if is_positive else self.colors['negative_bg']
        return f"""
            QFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: {self.dim.RADIUS_LG}px;
            }}
        """


# Global theme instance (light mode by default)
theme = Theme(COLORS_LIGHT)

# For backward compatibility
COLORS = COLORS_LIGHT
