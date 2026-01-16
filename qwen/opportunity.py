"""
Unified Opportunity Scanner

Combines watchlist, live prices, volatility analysis, and mispricing
detection into a single actionable dashboard.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np

from qwen.watchlist import Watchlist, WatchlistStock, Sector, RiskLevel
from qwen.data.yahoo import YahooDataProvider
from qwen.screener.volatility import VolatilityAnalyzer, VolatilityRegime
from qwen.screener.mispricing import MispricingScanner, MispricingOpportunity


@dataclass
class StockSnapshot:
    """Current snapshot of a stock with all relevant metrics."""

    symbol: str
    name: str
    sector: str
    price: float
    change_1d: float
    change_1d_pct: float
    change_5d_pct: float
    volume: int
    avg_volume: int
    volume_ratio: float
    iv_percentile: Optional[float] = None
    vol_regime: Optional[str] = None
    realized_vol_20d: Optional[float] = None
    iv_rv_ratio: Optional[float] = None
    vol_recommendation: Optional[str] = None
    risk_level: str = ""
    themes: list = None
    thesis: str = ""

    def __post_init__(self):
        if self.themes is None:
            self.themes = []


@dataclass
class OpportunitySummary:
    """Summary of all opportunities for a symbol."""

    symbol: str
    snapshot: StockSnapshot
    mispricing_count: int
    best_opportunity: Optional[MispricingOpportunity] = None
    opportunities: list = None

    def __post_init__(self):
        if self.opportunities is None:
            self.opportunities = []


class OpportunityScanner:
    """
    Unified scanner that brings together all analysis capabilities.

    Provides:
    - Live price snapshots for watchlist
    - Volatility regime analysis
    - Mispricing opportunity detection
    - Formatted output for quick review
    """

    def __init__(
        self,
        watchlist: Optional[Watchlist] = None,
        risk_free_rate: float = 0.05,
    ):
        """
        Initialize the scanner.

        Args:
            watchlist: Optional watchlist (uses default if not provided)
            risk_free_rate: Risk-free rate for options calculations
        """
        self.watchlist = watchlist or Watchlist()
        self.provider = YahooDataProvider()
        self.vol_analyzer = VolatilityAnalyzer(self.provider)
        self.mispricing_scanner = MispricingScanner(
            self.provider,
            risk_free_rate=risk_free_rate,
            min_edge_pct=5.0,
            min_volume=50,
        )

    def get_price_snapshot(self, stock: WatchlistStock) -> Optional[StockSnapshot]:
        """
        Get current price snapshot for a single stock.

        Args:
            stock: WatchlistStock to analyze

        Returns:
            StockSnapshot with current metrics
        """
        try:
            end = datetime.now()
            start = end - timedelta(days=30)

            history = self.provider.get_historical(stock.ticker, start, end)

            if history.empty or len(history) < 2:
                return None

            current_price = history['Close'].iloc[-1]
            prev_close = history['Close'].iloc[-2]

            change_1d = current_price - prev_close
            change_1d_pct = (change_1d / prev_close) * 100

            # 5-day change
            if len(history) >= 6:
                price_5d_ago = history['Close'].iloc[-6]
                change_5d_pct = ((current_price - price_5d_ago) / price_5d_ago) * 100
            else:
                change_5d_pct = 0

            # Volume analysis
            current_volume = int(history['Volume'].iloc[-1])
            avg_volume = int(history['Volume'].tail(20).mean())
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            return StockSnapshot(
                symbol=stock.ticker,
                name=stock.name,
                sector=stock.sector.value if hasattr(stock.sector, 'value') else str(stock.sector),
                price=current_price,
                change_1d=change_1d,
                change_1d_pct=change_1d_pct,
                change_5d_pct=change_5d_pct,
                volume=current_volume,
                avg_volume=avg_volume,
                volume_ratio=volume_ratio,
                risk_level=stock.risk_level.value if hasattr(stock.risk_level, 'value') else str(stock.risk_level),
                themes=stock.themes,
                thesis=stock.thesis,
            )

        except Exception as e:
            print(f"  Error fetching {stock.ticker}: {e}")
            return None

    def add_volatility_analysis(self, snapshot: StockSnapshot) -> StockSnapshot:
        """
        Add volatility metrics to a snapshot.

        Args:
            snapshot: StockSnapshot to enhance

        Returns:
            Enhanced snapshot with vol metrics
        """
        try:
            regime = self.vol_analyzer.analyze_symbol(snapshot.symbol)

            snapshot.iv_percentile = regime.iv_percentile
            snapshot.vol_regime = regime.vol_regime
            snapshot.realized_vol_20d = regime.realized_vol_20d
            snapshot.vol_recommendation = regime.recommendation

            if regime.realized_vol_20d > 0:
                snapshot.iv_rv_ratio = regime.current_iv / regime.realized_vol_20d

        except Exception as e:
            print(f"  Vol analysis error for {snapshot.symbol}: {e}")

        return snapshot

    def scan_watchlist(
        self,
        sectors: Optional[list[Sector]] = None,
        risk_levels: Optional[list[RiskLevel]] = None,
        themes: Optional[list[str]] = None,
        include_vol_analysis: bool = True,
        include_mispricing: bool = False,
        max_symbols: Optional[int] = None,
    ) -> list[StockSnapshot]:
        """
        Scan the watchlist and get snapshots for all stocks.

        Args:
            sectors: Filter by sectors
            risk_levels: Filter by risk levels
            themes: Filter by themes
            include_vol_analysis: Include volatility analysis
            include_mispricing: Include mispricing scan (slower)
            max_symbols: Limit number of symbols to scan

        Returns:
            List of StockSnapshots
        """
        # Apply filters
        stocks = self.watchlist.stocks

        if sectors:
            stocks = [s for s in stocks if s.sector in sectors]
        if risk_levels:
            stocks = [s for s in stocks if s.risk_level in risk_levels]
        if themes:
            stocks = [s for s in stocks if any(t in s.themes for t in themes)]
        if max_symbols:
            stocks = stocks[:max_symbols]

        snapshots = []
        total = len(stocks)

        print(f"\nScanning {total} symbols...")
        print("-" * 60)

        for i, stock in enumerate(stocks, 1):
            print(f"[{i}/{total}] {stock.ticker}...", end=" ")

            snapshot = self.get_price_snapshot(stock)
            if snapshot:
                if include_vol_analysis:
                    snapshot = self.add_volatility_analysis(snapshot)
                snapshots.append(snapshot)
                print(f"${snapshot.price:.2f} ({snapshot.change_1d_pct:+.1f}%)")
            else:
                print("FAILED")

        return snapshots

    def find_opportunities(
        self,
        symbols: Optional[list[str]] = None,
        min_confidence: float = 0.5,
    ) -> list[OpportunitySummary]:
        """
        Scan for mispricing opportunities.

        Args:
            symbols: Specific symbols to scan (uses watchlist if None)
            min_confidence: Minimum confidence threshold

        Returns:
            List of OpportunitySummary objects
        """
        if symbols is None:
            symbols = [s.ticker for s in self.watchlist.stocks]

        summaries = []

        print(f"\nScanning {len(symbols)} symbols for opportunities...")
        print("-" * 60)

        for symbol in symbols:
            print(f"Scanning {symbol}...", end=" ")

            # Get stock from watchlist if available
            stock = next((s for s in self.watchlist.stocks if s.ticker == symbol), None)

            # Get snapshot
            if stock:
                snapshot = self.get_price_snapshot(stock)
            else:
                # Create minimal snapshot for non-watchlist symbols
                try:
                    end = datetime.now()
                    start = end - timedelta(days=30)
                    history = self.provider.get_historical(symbol, start, end)
                    if not history.empty:
                        snapshot = StockSnapshot(
                            symbol=symbol,
                            name=symbol,
                            sector="Unknown",
                            price=history['Close'].iloc[-1],
                            change_1d=0,
                            change_1d_pct=0,
                            change_5d_pct=0,
                            volume=0,
                            avg_volume=0,
                            volume_ratio=1,
                        )
                    else:
                        snapshot = None
                except:
                    snapshot = None

            if not snapshot:
                print("FAILED (no price data)")
                continue

            # Scan for mispricing
            opportunities = self.mispricing_scanner.scan_symbol(symbol)
            opportunities = [o for o in opportunities if o.confidence >= min_confidence]

            if opportunities:
                best = max(opportunities, key=lambda o: abs(o.edge_pct))
                print(f"Found {len(opportunities)} opportunities!")
            else:
                best = None
                print("No opportunities")

            summaries.append(OpportunitySummary(
                symbol=symbol,
                snapshot=snapshot,
                mispricing_count=len(opportunities),
                best_opportunity=best,
                opportunities=opportunities,
            ))

        return summaries

    def format_price_table(self, snapshots: list[StockSnapshot]) -> str:
        """
        Format snapshots as a readable table.

        Args:
            snapshots: List of snapshots to format

        Returns:
            Formatted string table
        """
        if not snapshots:
            return "No data available."

        lines = []
        lines.append("")
        lines.append("=" * 100)
        lines.append("WATCHLIST SNAPSHOT")
        lines.append("=" * 100)
        lines.append("")

        # Header
        header = f"{'Symbol':<8} {'Price':>10} {'1D%':>8} {'5D%':>8} {'Vol Ratio':>10} {'IV%ile':>8} {'Regime':<12}"
        lines.append(header)
        lines.append("-" * 100)

        # Sort by 1D change
        snapshots_sorted = sorted(snapshots, key=lambda s: s.change_1d_pct, reverse=True)

        for s in snapshots_sorted:
            iv_pct = f"{s.iv_percentile:.0f}" if s.iv_percentile is not None else "N/A"
            regime = s.vol_regime or "N/A"

            # Color indicators (using ASCII)
            change_indicator = "+" if s.change_1d_pct > 0 else ""
            vol_indicator = "*" if s.volume_ratio > 1.5 else ""

            line = f"{s.symbol:<8} ${s.price:>8.2f} {change_indicator}{s.change_1d_pct:>7.1f}% {s.change_5d_pct:>+7.1f}% {s.volume_ratio:>9.1f}x {iv_pct:>7} {regime:<12}{vol_indicator}"
            lines.append(line)

        lines.append("")
        lines.append("-" * 100)
        lines.append(f"Total: {len(snapshots)} symbols | * = High volume | Sorted by 1D change")
        lines.append("")

        return "\n".join(lines)

    def format_vol_summary(self, snapshots: list[StockSnapshot]) -> str:
        """
        Format volatility regime summary.

        Args:
            snapshots: List of snapshots

        Returns:
            Formatted volatility summary
        """
        if not snapshots:
            return "No data available."

        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("VOLATILITY REGIME SUMMARY")
        lines.append("=" * 80)
        lines.append("")

        # Group by regime
        regimes = {}
        for s in snapshots:
            regime = s.vol_regime or "unknown"
            if regime not in regimes:
                regimes[regime] = []
            regimes[regime].append(s)

        regime_order = ['extreme', 'elevated', 'normal', 'normal_low', 'low', 'unknown']

        for regime in regime_order:
            if regime not in regimes:
                continue

            stocks = regimes[regime]
            lines.append(f"\n{regime.upper()} VOLATILITY ({len(stocks)} stocks):")
            lines.append("-" * 40)

            for s in sorted(stocks, key=lambda x: x.iv_percentile or 0, reverse=True):
                iv_pct = f"{s.iv_percentile:.0f}%" if s.iv_percentile else "N/A"
                lines.append(f"  {s.symbol:<8} IV Percentile: {iv_pct:>5}")

        lines.append("")

        # Trading recommendations
        lines.append("=" * 80)
        lines.append("TRADING RECOMMENDATIONS")
        lines.append("=" * 80)

        low_vol = [s for s in snapshots if s.vol_regime in ('low', 'normal_low')]
        high_vol = [s for s in snapshots if s.vol_regime in ('elevated', 'extreme')]

        if low_vol:
            lines.append("\nLOW VOL - Consider buying options (straddles, calendars):")
            for s in low_vol[:5]:
                lines.append(f"  {s.symbol}: {s.vol_recommendation or 'Buy vol strategies'}")

        if high_vol:
            lines.append("\nHIGH VOL - Consider selling premium (iron condors, credit spreads):")
            for s in high_vol[:5]:
                lines.append(f"  {s.symbol}: {s.vol_recommendation or 'Sell vol strategies'}")

        lines.append("")

        return "\n".join(lines)

    def format_opportunities(self, summaries: list[OpportunitySummary]) -> str:
        """
        Format opportunity summaries.

        Args:
            summaries: List of OpportunitySummary objects

        Returns:
            Formatted string
        """
        # Filter to only those with opportunities
        with_opps = [s for s in summaries if s.mispricing_count > 0]

        if not with_opps:
            return "\nNo mispricing opportunities found.\n"

        lines = []
        lines.append("")
        lines.append("=" * 100)
        lines.append("MISPRICING OPPORTUNITIES")
        lines.append("=" * 100)
        lines.append("")

        # Sort by best edge
        with_opps.sort(key=lambda s: abs(s.best_opportunity.edge_pct) if s.best_opportunity else 0, reverse=True)

        for summary in with_opps:
            lines.append(f"\n{summary.symbol} - {summary.mispricing_count} opportunities found")
            lines.append("-" * 60)

            for opp in sorted(summary.opportunities, key=lambda o: abs(o.edge_pct), reverse=True)[:3]:
                actionable = "[ACTIONABLE]" if opp.is_actionable else ""
                lines.append(f"  Type: {opp.opportunity_type}")
                lines.append(f"  {opp.description}")
                lines.append(f"  Edge: {opp.edge_pct:+.1f}% | Confidence: {opp.confidence:.0%} {actionable}")
                lines.append(f"  Trade: {opp.suggested_trade}")
                lines.append("")

        return "\n".join(lines)

    def run_full_scan(
        self,
        sectors: Optional[list[Sector]] = None,
        include_mispricing: bool = False,
        max_symbols: Optional[int] = None,
    ) -> str:
        """
        Run a full scan and return formatted output.

        Args:
            sectors: Filter by sectors
            include_mispricing: Include mispricing scan
            max_symbols: Limit symbols

        Returns:
            Complete formatted report
        """
        # Get snapshots
        snapshots = self.scan_watchlist(
            sectors=sectors,
            include_vol_analysis=True,
            include_mispricing=False,
            max_symbols=max_symbols,
        )

        output = []
        output.append(self.format_price_table(snapshots))
        output.append(self.format_vol_summary(snapshots))

        if include_mispricing:
            symbols = [s.symbol for s in snapshots]
            opportunities = self.find_opportunities(symbols)
            output.append(self.format_opportunities(opportunities))

        return "\n".join(output)


def quick_scan(max_symbols: int = 10) -> str:
    """
    Quick convenience function to scan watchlist.

    Args:
        max_symbols: Maximum symbols to scan

    Returns:
        Formatted report
    """
    scanner = OpportunityScanner()
    return scanner.run_full_scan(max_symbols=max_symbols)


if __name__ == "__main__":
    # Run a quick scan when executed directly
    print(quick_scan(10))
