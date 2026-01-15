---
title: Minimal Fast Dashboard (UI/UX + Performance) Design
date: 2026-01-15
status: approved
---

## Goal
Create a single Streamlit dashboard focused on clean UI/UX and faster load times.
Consolidate `qwen/dashboard.py` and `qwen/dashboard_pro.py` into one minimal,
fast dashboard with a compact metrics strip, a lightweight sortable table, and
one small chart. Minimize API calls and expensive re-renders.

## Scope
- One dashboard file: `qwen/dashboard.py`
- Simple header with timestamp and data source indicator
- Metrics strip with 4-6 KPIs
- Lightweight table with key columns and sortable controls
- Single small chart (sector performance or IV distribution)
- Sector + optional risk filter
- Cache-aware data fetching and derived metrics in one pass

Out of scope:
- Multi-tab layouts
- Multiple heavy charts
- Complex alerting or notifications

## Architecture
Three layers within the single file:
1. Providers: Yahoo (required), Alpaca (optional if available)
2. Data fetch + compute: cached functions for quotes + historical metrics
3. UI rendering: minimal layout, no heavy loops in widget render

Use `@st.cache_resource` for providers and watchlist, `@st.cache_data` for
data fetch functions with short TTL for quotes and longer TTL for history.

## Data Flow
1. Load watchlist and apply filters (sector, risk).
2. Fetch quotes in batch if Alpaca available; fallback to per-symbol Yahoo.
3. Fetch 30 days of historical data for calculations.
4. Compute derived metrics once per symbol: 1D%, 5D%, vol ratio, IV percentile,
   regime, sector/risk labels.
5. Return a single DataFrame plus summary KPIs for display.
6. UI only sorts/filters the DataFrame; no recomputation in widgets.

## UI Components
- Header: title, timestamp, data source badge
- Metrics strip: gainers, losers, avg change, high/low IV, symbol count
- Controls: sort by, sort order, sector and risk filters
- Table: compact columns for quick scanning
- Chart: one small chart for quick market context

## Error Handling
- Per-symbol fetch failures: skip and continue, warn minimally
- Empty DataFrame: clear error state + refresh hint
- Provider errors: fallback to Yahoo automatically

## Performance Plan
- Batch quotes when possible
- Short TTL for quotes (5-10s), longer TTL for history (60s)
- Avoid large Plotly charts; keep chart minimal
- Compute heavy stats once per symbol per fetch

## Testing
Manual checks:
- Load time with full watchlist
- Sorting and filtering correctness
- Cache behavior (timestamp updates, reduced calls)
- Empty/failed data handling
