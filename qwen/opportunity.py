"""
DEPRECATED: This module has been moved to qwen.screener.opportunity

This shim provides backward compatibility. Please update your imports to:
    from qwen.screener.opportunity import OpportunityScanner, OpportunitySummary
"""

import warnings

warnings.warn(
    "qwen.opportunity is deprecated. Use qwen.screener.opportunity instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location for backward compatibility
from qwen.screener.opportunity import (
    StockSnapshot,
    OpportunitySummary,
    OpportunityScanner,
    quick_scan,
)

__all__ = [
    "StockSnapshot",
    "OpportunitySummary",
    "OpportunityScanner",
    "quick_scan",
]
