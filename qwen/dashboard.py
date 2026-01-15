"""
Minimal Qwen Trading Dashboard

Fast, clean, and focused on quick scanning.
Run with: streamlit run qwen/dashboard.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
import time

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from qwen.config import config
from qwen.data.yahoo import YahooDataProvider
from qwen.dashboard_core import calculate_regime, summarize_metrics
from qwen.watchlist import Watchlist, RiskLevel

ALPACA_AVAILABLE = False
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

    if config.has_alpaca_credentials:
        ALPACA_AVAILABLE = True
except ImportError:
    pass


st.set_page_config(
    page_title="Qwen Minimal Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .app-header {
        padding: 0.5rem 0;
    }
    .app-header h1 {
        font-size: 26px;
        margin: 0;
    }
    .subtle {
        color: #9aa0a6;
        font-size: 12px;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def get_watchlist() -> Watchlist:
    return Watchlist()


@st.cache_resource
def get_yahoo_provider() -> YahooDataProvider:
    return YahooDataProvider()


@st.cache_resource
def get_alpaca_client() -> StockHistoricalDataClient | None:
    if not ALPACA_AVAILABLE:
        return None
    return StockHistoricalDataClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
    )


def get_data_source(client: StockHistoricalDataClient | None) -> str:
    return "Alpaca (Real-time)" if client else "Yahoo (15min delay)"


@st.cache_data(ttl=60)
def fetch_history(symbol: str) -> pd.DataFrame:
    provider = get_yahoo_provider()
    end = datetime.now()
    start = end - timedelta(days=30)
    return provider.get_historical(symbol, start, end)


@st.cache_data(ttl=10)
def fetch_market_data(symbols: tuple[str, ...]) -> pd.DataFrame:
    client = get_alpaca_client()
    quotes: dict[str, dict] = {}

    if client and symbols:
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=list(symbols))
            latest = client.get_stock_latest_quote(request)
            for symbol, quote in latest.items():
                bid = float(quote.bid_price)
                ask = float(quote.ask_price)
                price = (bid + ask) / 2 if bid and ask else (bid or ask)
                quotes[symbol] = {
                    "price": price,
                    "bid": bid,
                    "ask": ask,
                    "timestamp": quote.timestamp,
                    "source": "alpaca",
                }
        except Exception:
            quotes = {}

    watchlist = get_watchlist()
    stock_info = {s.ticker: s for s in watchlist.stocks}

    rows: list[dict] = []
    for symbol in symbols:
        history = fetch_history(symbol)
        if history.empty or len(history) < 2:
            continue

        quote = quotes.get(symbol, {})
        current_price = quote.get("price", float(history["Close"].iloc[-1]))
        prev_close = float(history["Close"].iloc[-2])
        open_price = float(history["Open"].iloc[-1])

        change_1d = current_price - prev_close
        change_1d_pct = (change_1d / prev_close) * 100 if prev_close else 0.0

        if len(history) >= 6:
            price_5d = float(history["Close"].iloc[-6])
            change_5d_pct = ((current_price - price_5d) / price_5d) * 100
        else:
            change_5d_pct = 0.0

        volume = int(history["Volume"].iloc[-1])
        avg_volume = float(history["Volume"].tail(20).mean())
        vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        returns = history["Close"].pct_change().dropna()
        rolling_vol = returns.rolling(20).std() * np.sqrt(252)
        rolling_vol = rolling_vol.dropna()
        if len(rolling_vol) > 0:
            current_rv = float(rolling_vol.iloc[-1])
            iv_percentile = float((rolling_vol < current_rv).mean() * 100)
        else:
            current_rv = 0.0
            iv_percentile = 50.0

        stock = stock_info.get(symbol)
        sector = stock.sector.value if stock else "Unknown"
        risk = stock.risk_level.value if stock else "Unknown"

        rows.append(
            {
                "Symbol": symbol,
                "Price": current_price,
                "Open": open_price,
                "Prev Close": prev_close,
                "1D %": change_1d_pct,
                "5D %": change_5d_pct,
                "Volume": volume,
                "Vol Ratio": vol_ratio,
                "IV %ile": iv_percentile,
                "RV 20D": current_rv * 100,
                "Regime": calculate_regime(iv_percentile),
                "Sector": sector,
                "Risk": risk,
                "Timestamp": quote.get("timestamp", datetime.now()),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    watchlist = get_watchlist()

    with st.sidebar:
        st.markdown("### Filters")
        sectors = ["All"] + sorted({s.sector.value for s in watchlist.stocks})
        selected_sector = st.selectbox("Sector", sectors)

        risks = ["All"] + [r.value for r in RiskLevel]
        selected_risk = st.selectbox("Risk", risks)

        st.markdown("---")
        auto_refresh = st.checkbox("Auto-refresh", value=False)
        refresh_interval = st.slider("Refresh (seconds)", 10, 300, 30)

    stocks = watchlist.stocks
    if selected_sector != "All":
        stocks = [s for s in stocks if s.sector.value == selected_sector]
    if selected_risk != "All":
        stocks = [s for s in stocks if s.risk_level.value == selected_risk]

    symbols = tuple(s.ticker for s in stocks)
    if not symbols:
        st.warning("No symbols match the selected filters.")
        return

    client = get_alpaca_client()
    data_source = get_data_source(client)

    st.markdown(
        f"""
<div class="app-header">
    <h1>Qwen Minimal Dashboard</h1>
    <div class="subtle">Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {data_source}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.spinner("Loading market data..."):
        df = fetch_market_data(symbols)

    if df.empty:
        st.error("No data returned. Check your connection or try again.")
        return

    metrics = summarize_metrics(df)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Gainers", metrics["gainers"])
    col2.metric("Losers", metrics["losers"])
    col3.metric("Avg Change", f"{metrics['avg_change']:+.2f}%")
    col4.metric("High IV", metrics["high_iv"])
    col5.metric("Low IV", metrics["low_iv"])
    col6.metric("Symbols", metrics["symbols"])

    st.markdown("---")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        sort_by = st.selectbox("Sort by", ["1D %", "5D %", "IV %ile", "Vol Ratio", "Symbol"])
    with col_b:
        ascending = st.selectbox("Order", ["Descending", "Ascending"]) == "Ascending"

    df_sorted = df.sort_values(sort_by, ascending=ascending)
    display_cols = ["Symbol", "Price", "1D %", "5D %", "Vol Ratio", "IV %ile", "Regime", "Sector"]
    df_display = df_sorted[display_cols].copy()

    df_display["Price"] = df_display["Price"].map(lambda x: f"${x:.2f}")
    df_display["1D %"] = df_display["1D %"].map(lambda x: f"{x:+.2f}%")
    df_display["5D %"] = df_display["5D %"].map(lambda x: f"{x:+.2f}%")
    df_display["Vol Ratio"] = df_display["Vol Ratio"].map(lambda x: f"{x:.1f}x")
    df_display["IV %ile"] = df_display["IV %ile"].map(lambda x: f"{x:.0f}%")

    st.dataframe(df_display, use_container_width=True, height=520)

    st.markdown("---")

    sector_perf = df.groupby("Sector")["1D %"].mean().reset_index()
    sector_perf = sector_perf.sort_values("1D %", ascending=True)
    fig = px.bar(
        sector_perf,
        x="1D %",
        y="Sector",
        orientation="h",
        title="Sector Performance (Avg 1D %)",
        color="1D %",
        color_continuous_scale=["#ff6b6b", "#ffd166", "#06d6a0"],
    )
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
