"""
Wheel Strategy Execution Engine

Implements the core wheel strategy logic:
1. Sell cash-secured puts
2. If assigned, hold shares
3. Sell covered calls
4. If called away, restart cycle
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from qwen.broker.alpaca_broker import AlpacaBroker
from qwen.broker.alpaca_options import AlpacaOptionsBroker
from qwen.broker.base import AccountInfo, BrokerOrder, OrderStatus
from qwen.data.yahoo import YahooDataProvider
from qwen.wheel.state import (
    WheelState,
    WheelPosition,
    WheelStateManager,
    OptionInfo,
    Trade,
)
from qwen.wheel.strike_selector import StrikeSelector, StrikeCandidate
from qwen.wheel.notifications import NotificationHub, NotificationLevel

logger = logging.getLogger(__name__)


@dataclass
class SymbolConfig:
    """Configuration for a single symbol in the wheel strategy."""

    symbol: str
    enabled: bool = True
    target_put_delta: float = 0.25
    target_call_delta: float = 0.30
    min_dte: int = 25
    max_dte: int = 45
    min_premium: float = 0.30
    max_positions: int = 1  # Max concurrent wheel positions


@dataclass
class WheelConfig:
    """Global wheel strategy configuration."""

    symbols: list[SymbolConfig]
    check_interval_minutes: int = 60
    market_hours_only: bool = True
    max_total_capital: float = 50000
    paper_mode: bool = True
    min_buying_power_reserve: float = 5000
    max_loss_per_position: float = 500
    stop_loss_percent: float = 0.50  # Close if option doubles against us
    roll_dte_threshold: int = 5  # Consider rolling at this DTE


class WheelEngine:
    """
    Core wheel strategy execution engine.

    Manages the complete lifecycle of wheel positions:
    - Selling cash-secured puts
    - Handling put assignments
    - Selling covered calls
    - Handling call assignments

    Thread-safe for use with schedulers.
    """

    def __init__(
        self,
        state_manager: WheelStateManager,
        notifications: NotificationHub,
        config: WheelConfig,
        options_broker: Optional[AlpacaOptionsBroker] = None,
        stock_broker: Optional[AlpacaBroker] = None,
        data_provider: Optional[YahooDataProvider] = None,
    ):
        """
        Initialize the wheel engine.

        Args:
            state_manager: State persistence manager
            notifications: Notification hub for alerts
            config: Wheel strategy configuration
            options_broker: Options broker (created if not provided)
            stock_broker: Stock broker (created if not provided)
            data_provider: Data provider (created if not provided)
        """
        self.state_manager = state_manager
        self.notifications = notifications
        self.config = config

        # Initialize brokers
        self.options_broker = options_broker or AlpacaOptionsBroker(
            paper=config.paper_mode
        )
        self.stock_broker = stock_broker or AlpacaBroker(
            paper=config.paper_mode
        )

        # Initialize data provider and strike selector
        self.data_provider = data_provider or YahooDataProvider()
        self.strike_selector = StrikeSelector(self.data_provider)

        logger.info(
            f"WheelEngine initialized: "
            f"{'PAPER' if config.paper_mode else 'LIVE'} mode, "
            f"{len(config.symbols)} symbols configured"
        )

    def _get_symbol_config(self, symbol: str) -> Optional[SymbolConfig]:
        """Get configuration for a symbol."""
        for cfg in self.config.symbols:
            if cfg.symbol == symbol:
                return cfg
        return None

    def _check_buying_power(self, required: float) -> bool:
        """Check if we have sufficient buying power."""
        account = self.stock_broker.get_account()
        available = account.buying_power - self.config.min_buying_power_reserve

        if available < required:
            logger.warning(
                f"Insufficient buying power: ${available:.2f} available, "
                f"${required:.2f} required"
            )
            return False
        return True

    def _build_occ_symbol(
        self,
        underlying: str,
        expiration: datetime,
        option_type: str,
        strike: float,
    ) -> str:
        """
        Build OCC option symbol.

        Format: AAPL240216C00185000
        """
        exp_str = expiration.strftime("%y%m%d")
        type_char = "C" if option_type == "call" else "P"
        strike_str = f"{int(strike * 1000):08d}"
        return f"{underlying}{exp_str}{type_char}{strike_str}"

    def check_and_execute(self, symbol: str) -> None:
        """
        Check position status and execute appropriate action.

        This is the main entry point called by the scheduler.

        Args:
            symbol: Stock ticker to check
        """
        symbol_config = self._get_symbol_config(symbol)
        if not symbol_config or not symbol_config.enabled:
            logger.debug(f"{symbol} is not enabled, skipping")
            return

        position = self.state_manager.get_position(symbol)
        logger.info(f"Checking {symbol}: state={position.state.value}")

        try:
            match position.state:
                case WheelState.IDLE:
                    self._handle_idle(symbol, position, symbol_config)
                case WheelState.PUT_OPEN:
                    self._handle_put_open(symbol, position, symbol_config)
                case WheelState.HOLDING_SHARES:
                    self._handle_holding_shares(symbol, position, symbol_config)
                case WheelState.CALL_OPEN:
                    self._handle_call_open(symbol, position, symbol_config)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)
            self.notifications.error_alert(
                f"Error processing {symbol}: {e}",
                {"symbol": symbol, "state": position.state.value},
            )

    def _handle_idle(
        self,
        symbol: str,
        position: WheelPosition,
        config: SymbolConfig,
    ) -> None:
        """
        Handle IDLE state - sell a new put.

        Args:
            symbol: Stock ticker
            position: Current wheel position
            config: Symbol configuration
        """
        logger.info(f"{symbol}: IDLE - looking for put to sell")

        # Find optimal put strike
        candidate = self.strike_selector.find_put_strike(
            symbol=symbol,
            target_delta=-abs(config.target_put_delta),
            min_dte=config.min_dte,
            max_dte=config.max_dte,
            min_premium=config.min_premium,
        )

        if not candidate:
            logger.warning(f"{symbol}: No suitable put found")
            return

        # Check buying power
        collateral = candidate.contract.strike * 100
        if not self._check_buying_power(collateral):
            return

        # Execute the trade
        self._sell_put(symbol, position, candidate)

    def _sell_put(
        self,
        symbol: str,
        position: WheelPosition,
        candidate: StrikeCandidate,
    ) -> None:
        """Sell a cash-secured put."""
        contract = candidate.contract
        occ_symbol = contract.symbol  # Yahoo already provides OCC format

        logger.info(
            f"{symbol}: Selling put - "
            f"strike=${contract.strike:.2f}, "
            f"premium=${contract.mid:.2f}, "
            f"DTE={candidate.days_to_expiration}"
        )

        try:
            # Submit sell order
            order = self.options_broker.sell_option(
                symbol=occ_symbol,
                qty=1,
                order_type="limit",
                limit_price=contract.bid,  # Use bid for faster fill
            )

            if order.status in (OrderStatus.FILLED, OrderStatus.ACCEPTED, OrderStatus.PENDING):
                # Update position state
                position.active_option = OptionInfo(
                    option_type="put",
                    strike=contract.strike,
                    expiration=contract.expiration.isoformat(),
                    premium=contract.mid,
                    quantity=-1,  # Short position
                    symbol=occ_symbol,
                    opened_at=datetime.now().isoformat(),
                )
                position.total_premium_collected += contract.mid * 100
                position.transition_to(WheelState.PUT_OPEN)

                # Record the trade
                trade = Trade(
                    timestamp=datetime.now().isoformat(),
                    action="sell_to_open",
                    symbol=occ_symbol,
                    option_type="put",
                    strike=contract.strike,
                    quantity=-1,
                    price=contract.mid,
                    premium=contract.mid * 100,
                    notes=f"DTE={candidate.days_to_expiration}, delta={candidate.delta:.3f}",
                )
                position.add_trade(trade)
                self.state_manager.update_position(position)

                # Send notification
                self.notifications.trade_alert(
                    action="SELL PUT",
                    symbol=symbol,
                    details={
                        "Strike": f"${contract.strike:.2f}",
                        "Premium": f"${contract.mid:.2f}",
                        "Expiration": contract.expiration.strftime("%Y-%m-%d"),
                        "DTE": candidate.days_to_expiration,
                        "Delta": f"{candidate.delta:.3f}",
                        "Order ID": order.id,
                    },
                )

                logger.info(f"{symbol}: Put sold successfully, order ID: {order.id}")

            else:
                logger.warning(f"{symbol}: Order not filled: {order.status}")

        except Exception as e:
            logger.error(f"{symbol}: Failed to sell put: {e}")
            self.notifications.error_alert(
                f"Failed to sell put for {symbol}: {e}",
                {"symbol": symbol, "strike": contract.strike},
            )

    def _handle_put_open(
        self,
        symbol: str,
        position: WheelPosition,
        config: SymbolConfig,
    ) -> None:
        """
        Handle PUT_OPEN state - check for expiration or assignment.

        Args:
            symbol: Stock ticker
            position: Current wheel position
            config: Symbol configuration
        """
        if not position.active_option:
            logger.error(f"{symbol}: PUT_OPEN but no active option!")
            position.transition_to(WheelState.IDLE)
            self.state_manager.update_position(position)
            return

        option = position.active_option
        dte = option.days_to_expiration

        logger.info(
            f"{symbol}: PUT_OPEN - "
            f"strike=${option.strike:.2f}, DTE={dte}"
        )

        # Check if expired
        if dte <= 0:
            self._handle_put_expiration(symbol, position)
            return

        # Check for early assignment by looking at positions
        stock_positions = self.stock_broker.get_positions()
        for pos in stock_positions:
            if pos.symbol == symbol and pos.qty >= 100:
                # We got assigned!
                self._handle_put_assignment(symbol, position, option.strike)
                return

        # Check if we should roll (approaching expiration and profitable)
        if dte <= self.config.roll_dte_threshold:
            logger.info(f"{symbol}: Approaching expiration, consider rolling")
            # For now, just let it expire - rolling logic can be added later

        # Check stop loss
        # TODO: Get current option price and compare to entry

    def _handle_put_expiration(
        self,
        symbol: str,
        position: WheelPosition,
    ) -> None:
        """Handle put expiration (expired worthless)."""
        option = position.active_option

        logger.info(f"{symbol}: Put expired worthless at ${option.strike:.2f}")

        # Record the trade
        trade = Trade(
            timestamp=datetime.now().isoformat(),
            action="expired",
            symbol=option.symbol,
            option_type="put",
            strike=option.strike,
            quantity=1,  # Closed position
            price=0.0,
            premium=option.premium * 100,  # Premium kept
            notes="Expired worthless - premium retained",
        )
        position.add_trade(trade)

        # Clear active option and return to IDLE
        position.active_option = None
        position.transition_to(WheelState.IDLE)
        self.state_manager.update_position(position)

        self.notifications.notify(
            f"{symbol} put expired worthless - kept ${option.premium * 100:.2f} premium",
            level=NotificationLevel.INFO,
            title=f"Put Expired: {symbol}",
            data={
                "Strike": f"${option.strike:.2f}",
                "Premium Kept": f"${option.premium * 100:.2f}",
            },
        )

    def _handle_put_assignment(
        self,
        symbol: str,
        position: WheelPosition,
        strike: float,
    ) -> None:
        """Handle put assignment - we now own shares."""
        option = position.active_option

        logger.info(f"{symbol}: Put assigned at ${strike:.2f}")

        # Update position
        position.shares_owned = 100
        position.cost_basis = strike - option.premium  # Effective cost basis
        position.active_option = None
        position.transition_to(WheelState.HOLDING_SHARES)

        # Record the trade
        trade = Trade(
            timestamp=datetime.now().isoformat(),
            action="assigned",
            symbol=symbol,
            option_type="put",
            strike=strike,
            quantity=100,
            price=strike,
            premium=option.premium * 100,
            notes=f"Put assigned - effective cost basis ${position.cost_basis:.2f}",
        )
        position.add_trade(trade)
        self.state_manager.update_position(position)

        self.notifications.assignment_alert(
            symbol=symbol,
            option_type="put",
            strike=strike,
            shares=100,
        )

    def _handle_holding_shares(
        self,
        symbol: str,
        position: WheelPosition,
        config: SymbolConfig,
    ) -> None:
        """
        Handle HOLDING_SHARES state - sell a covered call.

        Args:
            symbol: Stock ticker
            position: Current wheel position
            config: Symbol configuration
        """
        logger.info(
            f"{symbol}: HOLDING_SHARES - "
            f"{position.shares_owned} shares, cost basis=${position.cost_basis:.2f}"
        )

        # Verify we still own shares
        stock_positions = self.stock_broker.get_positions()
        shares_held = 0
        for pos in stock_positions:
            if pos.symbol == symbol:
                shares_held = int(pos.qty)
                break

        if shares_held < 100:
            logger.warning(f"{symbol}: Expected 100 shares but found {shares_held}")
            if shares_held == 0:
                position.shares_owned = 0
                position.transition_to(WheelState.IDLE)
                self.state_manager.update_position(position)
            return

        # Find optimal call strike
        candidate = self.strike_selector.find_call_strike(
            symbol=symbol,
            cost_basis=position.cost_basis,
            target_delta=config.target_call_delta,
            min_dte=config.min_dte,
            max_dte=config.max_dte,
            min_premium=config.min_premium,
        )

        if not candidate:
            logger.warning(f"{symbol}: No suitable call found above cost basis")
            return

        # Execute the trade
        self._sell_call(symbol, position, candidate)

    def _sell_call(
        self,
        symbol: str,
        position: WheelPosition,
        candidate: StrikeCandidate,
    ) -> None:
        """Sell a covered call."""
        contract = candidate.contract
        occ_symbol = contract.symbol

        logger.info(
            f"{symbol}: Selling call - "
            f"strike=${contract.strike:.2f}, "
            f"premium=${contract.mid:.2f}, "
            f"DTE={candidate.days_to_expiration}"
        )

        try:
            order = self.options_broker.sell_option(
                symbol=occ_symbol,
                qty=1,
                order_type="limit",
                limit_price=contract.bid,
            )

            if order.status in (OrderStatus.FILLED, OrderStatus.ACCEPTED, OrderStatus.PENDING):
                position.active_option = OptionInfo(
                    option_type="call",
                    strike=contract.strike,
                    expiration=contract.expiration.isoformat(),
                    premium=contract.mid,
                    quantity=-1,
                    symbol=occ_symbol,
                    opened_at=datetime.now().isoformat(),
                )
                position.total_premium_collected += contract.mid * 100
                position.transition_to(WheelState.CALL_OPEN)

                trade = Trade(
                    timestamp=datetime.now().isoformat(),
                    action="sell_to_open",
                    symbol=occ_symbol,
                    option_type="call",
                    strike=contract.strike,
                    quantity=-1,
                    price=contract.mid,
                    premium=contract.mid * 100,
                    notes=f"DTE={candidate.days_to_expiration}, delta={candidate.delta:.3f}",
                )
                position.add_trade(trade)
                self.state_manager.update_position(position)

                self.notifications.trade_alert(
                    action="SELL CALL",
                    symbol=symbol,
                    details={
                        "Strike": f"${contract.strike:.2f}",
                        "Premium": f"${contract.mid:.2f}",
                        "Expiration": contract.expiration.strftime("%Y-%m-%d"),
                        "DTE": candidate.days_to_expiration,
                        "Delta": f"{candidate.delta:.3f}",
                        "Cost Basis": f"${position.cost_basis:.2f}",
                    },
                )

                logger.info(f"{symbol}: Call sold successfully")

            else:
                logger.warning(f"{symbol}: Order not filled: {order.status}")

        except Exception as e:
            logger.error(f"{symbol}: Failed to sell call: {e}")
            self.notifications.error_alert(
                f"Failed to sell call for {symbol}: {e}",
                {"symbol": symbol, "strike": contract.strike},
            )

    def _handle_call_open(
        self,
        symbol: str,
        position: WheelPosition,
        config: SymbolConfig,
    ) -> None:
        """
        Handle CALL_OPEN state - check for expiration or assignment.

        Args:
            symbol: Stock ticker
            position: Current wheel position
            config: Symbol configuration
        """
        if not position.active_option:
            logger.error(f"{symbol}: CALL_OPEN but no active option!")
            position.transition_to(WheelState.HOLDING_SHARES)
            self.state_manager.update_position(position)
            return

        option = position.active_option
        dte = option.days_to_expiration

        logger.info(
            f"{symbol}: CALL_OPEN - "
            f"strike=${option.strike:.2f}, DTE={dte}"
        )

        # Check if expired
        if dte <= 0:
            self._handle_call_expiration(symbol, position)
            return

        # Check for early assignment by looking at stock positions
        stock_positions = self.stock_broker.get_positions()
        shares_held = 0
        for pos in stock_positions:
            if pos.symbol == symbol:
                shares_held = int(pos.qty)
                break

        if shares_held < 100:
            # Shares were called away
            self._handle_call_assignment(symbol, position, option.strike)

    def _handle_call_expiration(
        self,
        symbol: str,
        position: WheelPosition,
    ) -> None:
        """Handle call expiration (expired worthless)."""
        option = position.active_option

        logger.info(f"{symbol}: Call expired worthless at ${option.strike:.2f}")

        trade = Trade(
            timestamp=datetime.now().isoformat(),
            action="expired",
            symbol=option.symbol,
            option_type="call",
            strike=option.strike,
            quantity=1,
            price=0.0,
            premium=option.premium * 100,
            notes="Expired worthless - premium retained, still holding shares",
        )
        position.add_trade(trade)

        position.active_option = None
        position.transition_to(WheelState.HOLDING_SHARES)
        self.state_manager.update_position(position)

        self.notifications.notify(
            f"{symbol} call expired worthless - kept ${option.premium * 100:.2f}, selling new call",
            level=NotificationLevel.INFO,
            title=f"Call Expired: {symbol}",
        )

    def _handle_call_assignment(
        self,
        symbol: str,
        position: WheelPosition,
        strike: float,
    ) -> None:
        """Handle call assignment - shares were called away."""
        option = position.active_option

        # Calculate profit
        shares_profit = (strike - position.cost_basis) * 100
        total_cycle_premium = position.total_premium_collected

        logger.info(
            f"{symbol}: Call assigned at ${strike:.2f} - "
            f"profit=${shares_profit:.2f}, total premium=${total_cycle_premium:.2f}"
        )

        trade = Trade(
            timestamp=datetime.now().isoformat(),
            action="called_away",
            symbol=symbol,
            option_type="call",
            strike=strike,
            quantity=-100,
            price=strike,
            premium=option.premium * 100,
            notes=f"Shares called away - cycle complete, profit=${shares_profit + option.premium * 100:.2f}",
        )
        position.add_trade(trade)

        # Reset for next cycle
        position.shares_owned = 0
        position.cost_basis = 0.0
        position.active_option = None
        position.cycle_count += 1
        position.transition_to(WheelState.IDLE)
        self.state_manager.update_position(position)

        self.notifications.assignment_alert(
            symbol=symbol,
            option_type="call",
            strike=strike,
            shares=100,
        )

        self.notifications.notify(
            f"{symbol} wheel cycle #{position.cycle_count} complete! "
            f"Total premium collected: ${position.total_premium_collected:.2f}",
            level=NotificationLevel.INFO,
            title=f"Cycle Complete: {symbol}",
            data={
                "Cycles Completed": position.cycle_count,
                "Total Premium": f"${position.total_premium_collected:.2f}",
            },
        )

    def get_status_summary(self) -> dict:
        """Get a summary of all wheel positions."""
        positions = self.state_manager.get_all_positions()
        summary = self.state_manager.get_summary()

        active_symbols = []
        for symbol, pos in positions.items():
            if pos.state != WheelState.IDLE:
                active_symbols.append({
                    "symbol": symbol,
                    "state": pos.state.value,
                    "shares": pos.shares_owned,
                    "cost_basis": pos.cost_basis,
                    "premium_collected": pos.total_premium_collected,
                    "cycles": pos.cycle_count,
                })

        return {
            **summary,
            "active_details": active_symbols,
        }
