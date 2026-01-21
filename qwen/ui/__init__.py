"""UI components for Qwen."""

# Import dashboard components when available
try:
    from qwen.ui.dashboard import AlpacaDashboard, main as run_dashboard
    __all__ = ["AlpacaDashboard", "run_dashboard"]
except ImportError:
    # Streamlit or Alpaca may not be installed
    __all__ = []
