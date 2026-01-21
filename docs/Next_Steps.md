● Good - you want the full picture. Here's a prioritized improvement roadmap:

  1. Better Options Analysis (High Impact)

  Current gaps:
  - Basic Black-Scholes Greeks
  - No IV surface/skew modeling
  - No earnings event handling

  Improvements:
  - IV percentile rank using historical IV data
  - Skew analysis (put/call IV ratio by strike)
  - Term structure visualization
  - Earnings calendar integration (estimate IV crush)
  - Probability of profit (POP) calculations

  2. Automated Strategies (High Impact)

  What you could automate:
  - Wheel strategy: Auto-sell CSPs, roll or accept assignment, sell CCs
  - Alert system: Price/IV/volume triggers via Discord/email
  - Entry signals: IV rank thresholds, support/resistance levels
  - Position management: Stop losses, profit targets, auto-rolls

  Implementation approach:
  - Scheduler (APScheduler or cron) for periodic checks
  - State machine for wheel lifecycle
  - Webhook integration for alerts

  3. Portfolio Tracking (Medium Impact)

  Current state: Basic PortfolioTracker exists

  Improvements:
  - Sync positions from Alpaca automatically
  - Historical P&L curves
  - Greeks aggregation (portfolio delta, theta, etc.)
  - Tax lot tracking with wash sale detection
  - CSV/Excel export for tax prep

  4. Backtesting Enhancements (Medium Impact)

  Current gaps:
  - No options backtesting (only equity strategies)
  - Idealized fills

  Improvements:
  - Historical options data (need data source - CBOE or OptionMetrics is expensive)
  - Bid-ask spread modeling for realistic fills
  - Slippage based on volume
  - Commission modeling

  ---
  My recommendation: Start with Automated Strategies - specifically a wheel automation tool. It's the highest practical value since you're already tracking wheel candidates (SSYS notebook). Want me to sketch out an implementation plan for that?

   What Was Built

  qwen/wheel/
  ├── __init__.py          # Module exports
  ├── state.py             # State persistence (JSON-based)
  ├── strike_selector.py   # Delta-based strike selection
  ├── notifications.py     # Console, Discord, Email alerts
  ├── config.py            # YAML config loader
  ├── engine.py            # Core wheel execution logic
  ├── scheduler.py         # APScheduler daemon
  └── cli.py               # Command-line interface

  CLI Commands Available

  # Analyze a symbol's wheel opportunity
  python -m qwen.wheel.cli analyze SSYS

  # Check current status
  python -m qwen.wheel.cli status

  # Start the automation daemon
  python -m qwen.wheel.cli start

  # Manual check for a single symbol
  python -m qwen.wheel.cli check SSYS

  # View trade history
  python -m qwen.wheel.cli trades

  Quick Test Results

  SSYS Wheel Analysis:
  - PUT: $10 strike, $0.40 premium, 35 DTE → 41.7% annualized ROI
  - CALL: $12.50 strike, $0.45 premium, 35 DTE → 42.0% annualized ROI
  - Estimated Wheel Return: ~42% annualized

  Next Steps

  1. Install dependencies (if not already):
  pip install -e ".[wheel-automation]"
  2. Edit the config (wheel_config.yaml) to set your preferences
  3. Test in paper mode first:
  python -m qwen.wheel.cli start
  4. Set up Discord webhook (optional) by adding DISCORD_WEBHOOK_URL to your .env

  The automation defaults to paper mode for safety. Want me to commit these changes to git?