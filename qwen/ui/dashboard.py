"""
Qwen Pro Trading Dashboard - Real-time Alpaca Integration

One-page dashboard showing:
- Live account positions with real-time P&L
- Watchlist with streaming price updates

Run with: streamlit run qwen/ui/dashboard.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
import time

from qwen.data.watchlist import Watchlist
from qwen.config import config

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest, StockLatestBarRequest
    from alpaca.data.live import StockDataStream
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Qwen Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Modern glassmorphic CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    .stApp {
        background:
            radial-gradient(ellipse at 10% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 90% 80%, rgba(168, 85, 247, 0.06) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(6, 182, 212, 0.04) 0%, transparent 70%),
            linear-gradient(180deg, #0c0f14 0%, #111827 50%, #0c0f14 100%);
        background-attachment: fixed;
        min-height: 100vh;
    }

    .main .block-container {
        padding: 1.5rem 3rem;
        max-width: 100%;
    }

    /* Header */
    .terminal-header {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.6) 100%);
        backdrop-filter: blur(20px);
        padding: 20px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
        position: relative;
    }

    .terminal-header::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(251, 191, 36, 0.5) 50%, transparent 100%);
    }

    .terminal-header h1 {
        color: #fbbf24;
        font-family: 'DM Sans', sans-serif;
        font-size: 28px;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .terminal-header .subtitle {
        color: rgba(148, 163, 184, 0.8);
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .terminal-header .status-row {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-top: 8px;
    }

    .status-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .status-badge.live {
        background: rgba(74, 222, 128, 0.15);
        color: #4ade80;
        border: 1px solid rgba(74, 222, 128, 0.3);
    }

    .status-badge.live::before {
        content: "";
        width: 6px;
        height: 6px;
        background: #4ade80;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }

    .status-badge.paper {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }

    .status-badge.closed {
        background: rgba(248, 113, 113, 0.15);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }

    @keyframes pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }

    /* Account metrics */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.5) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
    }

    .metric-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(148, 163, 184, 0.15) 50%, transparent 100%);
    }

    .metric-card .label {
        color: rgba(148, 163, 184, 0.7);
        font-family: 'DM Sans', sans-serif;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 6px;
    }

    .metric-card .value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 700;
        color: #f8fafc;
    }

    .metric-card .value.positive { color: #4ade80; }
    .metric-card .value.negative { color: #f87171; }
    .metric-card .value.accent { color: #fbbf24; }

    .metric-card .change {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        margin-top: 4px;
    }

    /* Section headers */
    .section-header {
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        font-weight: 700;
        color: #fbbf24;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 24px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(251, 191, 36, 0.2);
    }

    /* Tables */
    .data-table {
        font-family: 'JetBrains Mono', monospace;
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 41, 59, 0.4) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        font-size: 13px;
        overflow: hidden;
    }

    .data-table th {
        background: rgba(15, 23, 42, 0.8);
        color: rgba(148, 163, 184, 0.7);
        padding: 14px 16px;
        text-align: left;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 10px;
        letter-spacing: 1px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }

    .data-table td {
        padding: 12px 16px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.05);
        color: #e2e8f0;
    }

    .data-table tbody tr:hover {
        background: rgba(251, 191, 36, 0.03);
    }

    .data-table tbody tr:last-child td {
        border-bottom: none;
    }

    /* Cell styles */
    .symbol { color: #fbbf24; font-weight: 700; }
    .price { color: #f8fafc; font-weight: 600; }
    .positive { color: #4ade80 !important; }
    .negative { color: #f87171 !important; }
    .neutral { color: #64748b; }
    .muted { color: #475569; font-size: 11px; }

    /* Sectors container - 2 column layout */
    .sectors-container {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }

    /* Sector groups */
    .sector-group {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.5) 0%, rgba(30, 41, 59, 0.3) 100%);
        border: 1px solid rgba(148, 163, 184, 0.06);
        border-radius: 10px;
        padding: 12px;
    }

    .sector-header {
        font-family: 'DM Sans', sans-serif;
        font-size: 10px;
        font-weight: 600;
        color: #fbbf24;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.08);
    }

    /* Watchlist grid inside each sector */
    .watchlist-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
        gap: 6px;
    }

    .stock-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.05);
        border-radius: 6px;
        padding: 8px;
        transition: all 0.15s ease;
    }

    .stock-card:hover {
        border-color: rgba(251, 191, 36, 0.3);
        background: rgba(251, 191, 36, 0.05);
    }

    .stock-card .ticker {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 700;
        color: #fbbf24;
    }

    .stock-card .price-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 2px;
    }

    .stock-card .current-price {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
    }

    .stock-card .change {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        font-weight: 600;
    }

    .stock-card .change.up { color: #4ade80; }
    .stock-card .change.down { color: #f87171; }

    /* Hide Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #64748b;
        font-family: 'DM Sans', sans-serif;
    }

    .empty-state .icon {
        font-size: 32px;
        margin-bottom: 12px;
        opacity: 0.5;
    }

    /* Streamlit overrides */
    .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(148, 163, 184, 0.1) !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div {
        background: rgba(15, 23, 42, 0.8) !important;
        border-color: rgba(148, 163, 184, 0.15) !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.2) 0%, rgba(245, 158, 11, 0.1) 100%) !important;
        border: 1px solid rgba(251, 191, 36, 0.3) !important;
        border-radius: 8px !important;
        color: #fbbf24 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.3) 0%, rgba(245, 158, 11, 0.2) 100%) !important;
        border-color: rgba(251, 191, 36, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)


class AlpacaDashboard:
    """Alpaca-powered real-time dashboard."""

    def __init__(self):
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py is required. Install with: pip install alpaca-py")

        if not config.alpaca_api_key or not config.alpaca_secret_key:
            raise ValueError("Alpaca credentials required. Set ALPACA_API_KEY and ALPACA_SECRET_KEY.")

        self.trading_client = TradingClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
            paper=config.alpaca_paper,
        )
        self.data_client = StockHistoricalDataClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
        )
        self.is_paper = config.alpaca_paper

    def get_account(self) -> dict:
        """Get account information."""
        account = self.trading_client.get_account()
        return {
            "portfolio_value": float(account.portfolio_value),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "long_market_value": float(account.long_market_value),
            "day_change": float(account.equity) - float(account.last_equity),
            "day_change_pct": ((float(account.equity) - float(account.last_equity)) / float(account.last_equity) * 100) if float(account.last_equity) > 0 else 0,
        }

    def get_positions(self) -> list[dict]:
        """Get all open positions."""
        positions = self.trading_client.get_all_positions()
        return [
            {
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "avg_entry": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_plpc": float(pos.unrealized_plpc) * 100,
                "cost_basis": float(pos.cost_basis),
                "side": "Long" if float(pos.qty) > 0 else "Short",
            }
            for pos in positions
        ]

    def is_market_open(self) -> bool:
        """Check if market is open."""
        clock = self.trading_client.get_clock()
        return clock.is_open

    def get_market_status(self) -> dict:
        """Get market status info."""
        clock = self.trading_client.get_clock()
        return {
            "is_open": clock.is_open,
            "next_open": clock.next_open,
            "next_close": clock.next_close,
        }

    def get_quotes(self, symbols: list[str]) -> dict:
        """Get latest quotes for symbols."""
        if not symbols:
            return {}

        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.data_client.get_stock_latest_quote(request)

            results = {}
            for symbol, quote in quotes.items():
                bid = float(quote.bid_price) if quote.bid_price else 0
                ask = float(quote.ask_price) if quote.ask_price else 0
                mid = (bid + ask) / 2 if bid and ask else bid or ask

                results[symbol] = {
                    "symbol": symbol,
                    "bid": bid,
                    "ask": ask,
                    "price": mid,
                    "spread": ask - bid if bid and ask else 0,
                    "timestamp": quote.timestamp,
                }
            return results
        except Exception as e:
            st.error(f"Quote fetch error: {e}")
            return {}

    def get_bars(self, symbols: list[str]) -> dict:
        """Get latest bars for change calculation."""
        if not symbols:
            return {}

        try:
            request = StockLatestBarRequest(symbol_or_symbols=symbols)
            bars = self.data_client.get_stock_latest_bar(request)

            results = {}
            for symbol, bar in bars.items():
                results[symbol] = {
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume),
                    "vwap": float(bar.vwap) if bar.vwap else float(bar.close),
                }
            return results
        except Exception as e:
            return {}


@st.cache_resource
def get_dashboard():
    """Get cached dashboard instance."""
    return AlpacaDashboard()


@st.cache_resource
def get_watchlist():
    """Get cached watchlist."""
    return Watchlist()


def render_positions_table(positions: list[dict]) -> str:
    """Render positions as HTML table."""
    if not positions:
        return '<div class="empty-state"><div class="icon">📊</div><div>No open positions</div></div>'

    rows = []
    for pos in positions:
        pl_class = "positive" if pos["unrealized_pl"] >= 0 else "negative"
        pl_sign = "+" if pos["unrealized_pl"] >= 0 else ""

        row = (
            f'<tr>'
            f'<td class="symbol">{pos["symbol"]}</td>'
            f'<td>{pos["side"]}</td>'
            f'<td>{pos["qty"]:.0f}</td>'
            f'<td class="price">${pos["avg_entry"]:.2f}</td>'
            f'<td class="price">${pos["current_price"]:.2f}</td>'
            f'<td class="price">${pos["market_value"]:,.2f}</td>'
            f'<td class="{pl_class}">{pl_sign}${pos["unrealized_pl"]:,.2f}</td>'
            f'<td class="{pl_class}">{pl_sign}{pos["unrealized_plpc"]:.2f}%</td>'
            f'</tr>'
        )
        rows.append(row)

    return (
        '<table class="data-table">'
        '<thead><tr>'
        '<th>Symbol</th><th>Side</th><th>Qty</th><th>Avg Entry</th>'
        '<th>Current</th><th>Mkt Value</th><th>P&L $</th><th>P&L %</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
    )


def render_watchlist_grid(quotes: dict, bars: dict, watchlist_stocks: dict) -> str:
    """Render watchlist as compact card grid grouped by sector."""
    if not quotes:
        return '<div class="empty-state"><div class="icon">📈</div><div>Loading quotes...</div></div>'

    # Group by sector
    sectors = {}
    for symbol, quote in quotes.items():
        stock_info = watchlist_stocks.get(symbol)
        sector = stock_info.sector.value if stock_info else "Other"
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append((symbol, quote))

    # Sort sectors and stocks within each sector
    html_parts = []
    for sector in sorted(sectors.keys()):
        stocks = sorted(sectors[sector], key=lambda x: x[0])

        cards = []
        for symbol, quote in stocks:
            bar = bars.get(symbol, {})

            price = quote.get("price", 0)
            open_price = bar.get("open", price)
            change_pct = ((price - open_price) / open_price * 100) if open_price else 0

            change_class = "up" if change_pct >= 0 else "down"
            change_sign = "+" if change_pct >= 0 else ""

            card = (
                f'<div class="stock-card">'
                f'<div class="ticker">{symbol}</div>'
                f'<div class="price-row">'
                f'<span class="current-price">${price:.2f}</span>'
                f'<span class="change {change_class}">{change_sign}{change_pct:.1f}%</span>'
                f'</div>'
                f'</div>'
            )
            cards.append(card)

        section = (
            f'<div class="sector-group">'
            f'<div class="sector-header">{sector}</div>'
            f'<div class="watchlist-grid">{"".join(cards)}</div>'
            f'</div>'
        )
        html_parts.append(section)

    return f'<div class="sectors-container">{"".join(html_parts)}</div>'


def main():
    # Check for Alpaca availability
    if not ALPACA_AVAILABLE:
        st.error("alpaca-py is not installed. Install with: pip install alpaca-py")
        return

    if not config.alpaca_api_key or not config.alpaca_secret_key:
        st.error("Alpaca credentials not found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.")
        return

    # Initialize dashboard
    try:
        dashboard = get_dashboard()
    except Exception as e:
        st.error(f"Failed to initialize dashboard: {e}")
        return

    # Sidebar
    with st.sidebar:
        st.markdown("### Settings")
        refresh_rate = st.selectbox(
            "Refresh Rate",
            options=[1, 2, 3, 5, 10],
            index=1,
            format_func=lambda x: f"{x}s"
        )
        auto_refresh = st.checkbox("Auto Refresh", value=True)

        st.markdown("---")

        if st.button("Force Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Get data
    account = dashboard.get_account()
    positions = dashboard.get_positions()
    market_status = dashboard.get_market_status()
    watchlist = get_watchlist()
    symbols = watchlist.tickers

    # Get quotes and bars
    quotes = dashboard.get_quotes(symbols)
    bars = dashboard.get_bars(symbols)

    # Create stock info lookup
    stock_info_map = {s.ticker: s for s in watchlist.stocks}

    # Header
    now = datetime.now()
    market_badge = "live" if market_status["is_open"] else "closed"
    market_text = "MARKET OPEN" if market_status["is_open"] else "MARKET CLOSED"
    mode_badge = "paper" if dashboard.is_paper else "live"
    mode_text = "PAPER" if dashboard.is_paper else "LIVE"

    st.markdown(f"""
    <div class="terminal-header">
        <div class="subtitle">Real-time Alpaca Dashboard</div>
        <h1>QWEN TERMINAL</h1>
        <div class="status-row">
            <span style="color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                {now.strftime('%a %b %d, %Y')} · {now.strftime('%H:%M:%S')}
            </span>
            <span class="status-badge {market_badge}">{market_text}</span>
            <span class="status-badge {mode_badge}">{mode_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Account metrics
    day_change_class = "positive" if account["day_change"] >= 0 else "negative"
    day_change_sign = "+" if account["day_change"] >= 0 else ""

    # Calculate total unrealized P&L
    total_unrealized = sum(p["unrealized_pl"] for p in positions)
    unrealized_class = "positive" if total_unrealized >= 0 else "negative"
    unrealized_sign = "+" if total_unrealized >= 0 else ""

    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="label">Portfolio Value</div>
            <div class="value accent">${account['portfolio_value']:,.2f}</div>
            <div class="change {day_change_class}">{day_change_sign}${account['day_change']:,.2f} ({day_change_sign}{account['day_change_pct']:.2f}%)</div>
        </div>
        <div class="metric-card">
            <div class="label">Cash</div>
            <div class="value">${account['cash']:,.2f}</div>
        </div>
        <div class="metric-card">
            <div class="label">Buying Power</div>
            <div class="value">${account['buying_power']:,.2f}</div>
        </div>
        <div class="metric-card">
            <div class="label">Long Market Value</div>
            <div class="value">${account['long_market_value']:,.2f}</div>
        </div>
        <div class="metric-card">
            <div class="label">Unrealized P&L</div>
            <div class="value {unrealized_class}">{unrealized_sign}${total_unrealized:,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Positions section
    st.markdown('<div class="section-header">Live Positions</div>', unsafe_allow_html=True)
    positions_html = render_positions_table(positions)
    st.markdown(positions_html, unsafe_allow_html=True)

    # Watchlist section
    st.markdown('<div class="section-header">Watchlist</div>', unsafe_allow_html=True)
    watchlist_html = render_watchlist_grid(quotes, bars, stock_info_map)
    st.markdown(watchlist_html, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div style="text-align: center; margin-top: 32px; padding: 16px; color: #475569; font-family: 'JetBrains Mono', monospace; font-size: 11px;">
        {len(positions)} positions · {len(quotes)} watchlist quotes · Alpaca API
    </div>
    """, unsafe_allow_html=True)

    # Auto refresh
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()


if __name__ == "__main__":
    main()
