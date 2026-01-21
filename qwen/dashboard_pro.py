"""
DEPRECATED: This module has been moved to qwen.ui.dashboard

This shim provides backward compatibility. Please update your imports to:
    from qwen.ui.dashboard import AlpacaDashboard, main

Run the dashboard with: streamlit run qwen/ui/dashboard.py
"""

import warnings

warnings.warn(
    "qwen.dashboard_pro is deprecated. Use qwen.ui.dashboard instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility
try:
    from qwen.ui.dashboard import (
        AlpacaDashboard,
        get_dashboard,
        get_watchlist,
        render_positions_table,
        render_watchlist_grid,
        main,
    )

    __all__ = [
        "AlpacaDashboard",
        "get_dashboard",
        "get_watchlist",
        "render_positions_table",
        "render_watchlist_grid",
        "main",
    ]
except ImportError:
    # Streamlit or Alpaca may not be installed
    __all__ = []

if __name__ == "__main__":
    main()
