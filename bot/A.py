"""
A-Bot: Crypto Sniper
Version: 3.0.0

Key principles:
- Signal-driven: WAITS for TradingView buy/sell signals
- Uses 15% of capital in BTC Mode, 0% in GOLD Mode
- Stakes idle funds while waiting for signals
- Manages up to 6 slots
- Seat warmer logic: >3 empty → auto-buy highest yield, <2 empty → sell oldest (FIFO)
"""
import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ABot:
    """
    Sniper Bot - Waits for TradingView signals and stakes idle funds
    """

    def __init__(self, config: dict, exchanges: Dict, staking_manager=None, fee_manager=None):
        self.config = config
        self.exchanges = exchanges
        self.staking_manager = staking_manager
        self.fee_manager = fee_manager
        
        # Slot configuration
        staking_config = config.get('staking', {})
        self.max_slots = staking_config.get('slots', 6)
        self.target_coins = staking_config.get('target_coins', ['ADA', 'ETH', 'SOL', 'DOT', 'ATOM'])
        self.seat_warmer_empty_threshold = staking_config.get('seat_warmer_empty_threshold', 3)
        self.seat_warmer_full_threshold = staking_config.get('seat_warmer_full_threshold', 2)
        
        # Allowed coins from env
        allowed_coins_str = os.getenv('A_BOT_COINS', 'BTC,ETH,SOL,XRP,HBAR,LINK')
        self.allowed_coins = [c.strip().upper() for c in allowed_coins_str.split(',')]
        
        # Default stake coin
        self.default_stake_coin = os.getenv('DEFAULT_STAKE_COIN', 'ETH').upper()
        
        # Positions: OrderedDict to maintain FIFO order
        # {coin: {'amount': Decimal, 'exchange': str, 'staked': bool, 'timestamp': datetime, 'is_seat_warmer': bool}}
        self.positions = OrderedDict()
        
        # State
        self.running = False
        self.signals_received = 0
        self.trades_executed = 0
        
        logger.info(f"🎯 A-Bot initialized. Max slots: {self.max_slots}, Allowed coins: {self.allowed_coins}")

    def get_empty_slots(self) -> int:
        """Get number of empty slots"""
        return self.max_slots - len(self.positions)

    def handle_signal(self, action: str, coin: str, data: dict = None) -> bool:
        """
        Handle incoming TradingView signal
        
        Args:
            action: 'BUY' or 'SELL'
            coin: Coin symbol (e.g., 'ETH')
            data: Additional signal data
        
        Returns:
            True if signal was processed successfully
        """
        self.signals_received += 1
        action = action.upper()
        coin = coin.upper()
        
        logger.info(f"🎯 A-Bot received signal: {action} {coin}")
        
        if coin not in self.allowed_coins:
            logger.warning(f"⚠️ {coin} not in allowed coins list, ignoring signal")
            return False
        
        if action == 'BUY':
            return self._execute_buy(coin)
        elif action == 'SELL':
            return self._execute_sell(coin)
        else:
            logger.warning(f"⚠️ Unknown action: {action}")
            return False

    def _execute_buy(self, coin: str) -> bool:
        """Execute a buy signal"""
        if len(self.positions) >= self.max_slots:
            logger.warning(f"⚠️ All {self.max_slots} slots full, cannot buy {coin}")
            return False
        
        if coin in self.positions:
            logger.warning(f"⚠️ Already holding {coin}, ignoring buy signal")
            return False
        
        # Find best exchange to buy
        best_exchange, best_price = self._find_best_buy_price(coin)
        if not best_exchange:
            logger.error(f"❌ Could not find exchange to buy {coin}")
            return False
        
        # Calculate amount (equal allocation per slot)
        # This will be set by the orchestrator based on allocated capital
        amount = Decimal('0')  # Placeholder - orchestrator sets this
        
        logger.info(f"🎯 Executing BUY {coin} on {best_exchange} @ ${best_price}")
        
        # Add position
        self.positions[coin] = {
            'amount': amount,
            'exchange': best_exchange,
            'buy_price': best_price,
            'staked': False,
            'timestamp': datetime.now(),
            'is_seat_warmer': False
        }
        
        self.trades_executed += 1
        return True

    def _execute_sell(self, coin: str) -> bool:
        """Execute a sell signal"""
        if coin not in self.positions:
            logger.warning(f"⚠️ Not holding {coin}, ignoring sell signal")
            return False
        
        position = self.positions[coin]
        
        # Unstake if staked
        if position['staked'] and self.staking_manager:
            logger.info(f"📤 Unstaking {coin} before sell")
            # self.staking_manager.unstake(position['exchange'], coin, position['amount'])
        
        logger.info(f"🎯 Executing SELL {coin} on {position['exchange']}")
        
        # Remove position
        del self.positions[coin]
        
        self.trades_executed += 1
        return True

    def _find_best_buy_price(self, coin: str) -> tuple:
        """Find the exchange with the best (lowest) buy price"""
        best_exchange = None
        best_price = None
        
        pair = f"{coin}/USDT"
        
        for ex_name, exchange in self.exchanges.items():
            try:
                # This would be async in real implementation
                ticker = exchange.fetch_ticker(pair) if hasattr(exchange, 'fetch_ticker') else None
                if ticker and ticker.get('ask'):
                    price = Decimal(str(ticker['ask']))
                    if best_price is None or price < best_price:
                        best_price = price
                        best_exchange = ex_name
            except Exception as e:
                logger.debug(f"Error fetching {pair} from {ex_name}: {e}")
                continue
        
        return best_exchange, best_price

    def check_seat_warmers(self, allocated_capital: Decimal) -> None:
        """
        Check and manage seat warmer positions
        
        - If >3 slots empty: auto-buy highest yield coin to "warm the seat"
        - If <2 slots empty: sell oldest seat warmer (FIFO)
        """
        empty_slots = self.get_empty_slots()
        
        # Too many empty - add seat warmer
        if empty_slots > self.seat_warmer_empty_threshold:
            logger.info(f"🪑 {empty_slots} empty slots, adding seat warmer")
            self._add_seat_warmer(allocated_capital / self.max_slots)
        
        # Too few empty - remove oldest seat warmer
        elif empty_slots < self.seat_warmer_full_threshold:
            self._remove_oldest_seat_warmer()

    def _add_seat_warmer(self, amount_usd: Decimal) -> bool:
        """Add a seat warmer position with highest yield coin"""
        # Use default stake coin or find highest yield
        coin = self.default_stake_coin
        
        if coin in self.positions:
            # Try next target coin
            for c in self.target_coins:
                if c not in self.positions:
                    coin = c
                    break
        
        if coin in self.positions:
            logger.warning("⚠️ All target coins already held, cannot add seat warmer")
            return False
        
        best_exchange, best_price = self._find_best_buy_price(coin)
        if not best_exchange or not best_price:
            return False
        
        amount = amount_usd / best_price
        
        logger.info(f"🪑 Adding seat warmer: {amount:.6f} {coin} on {best_exchange}")
        
        self.positions[coin] = {
            'amount': amount,
            'exchange': best_exchange,
            'buy_price': best_price,
            'staked': True,  # Seat warmers are staked
            'timestamp': datetime.now(),
            'is_seat_warmer': True
        }
        
        return True

    def _remove_oldest_seat_warmer(self) -> bool:
        """Remove the oldest seat warmer position (FIFO)"""
        # Find oldest seat warmer
        for coin, position in self.positions.items():
            if position.get('is_seat_warmer'):
                logger.info(f"🪑 Removing oldest seat warmer: {coin}")
                del self.positions[coin]
                return True
        
        logger.debug("No seat warmers to remove")
        return False

    def stake_idle_funds(self) -> None:
        """Stake any unstaked positions"""
        if not self.staking_manager:
            return
        
        for coin, position in self.positions.items():
            if not position['staked']:
                logger.info(f"📥 Staking idle {coin}")
                # self.staking_manager.stake(position['exchange'], coin, position['amount'])
                position['staked'] = True

    def liquidate_all(self) -> None:
        """Liquidate all positions (called on mode change to GOLD)"""
        logger.info("🔄 A-Bot liquidating all positions for mode change")
        for coin in list(self.positions.keys()):
            self._execute_sell(coin)

    def get_status(self) -> Dict:
        """Get current A-Bot status for dashboard"""
        return {
            'running': self.running,
            'slots_used': len(self.positions),
            'slots_total': self.max_slots,
            'slots_empty': self.get_empty_slots(),
            'positions': {coin: {
                'exchange': pos['exchange'],
                'staked': pos['staked'],
                'is_seat_warmer': pos.get('is_seat_warmer', False)
            } for coin, pos in self.positions.items()},
            'signals_received': self.signals_received,
            'trades_executed': self.trades_executed,
            'allowed_coins': self.allowed_coins
        }
