import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
from collections import OrderedDict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ABot:
    def __init__(self, config: dict, exchanges: Dict, staking_manager=None, fee_manager=None):
        self.config = config
        self.exchanges = exchanges
        self.staking_manager = staking_manager
        self.fee_manager = fee_manager
        staking_config = config.get('staking', {})
        self.max_slots = staking_config.get('slots', 6)
        self.seat_warmer_empty_threshold = staking_config.get('seat_warmer_empty_threshold', 3)
        self.seat_warmer_full_threshold = staking_config.get('seat_warmer_full_threshold', 2)
        self.allowed_coins = []  # Dynamic
        self.default_stake_coin = None  # Dynamic
        self.positions = OrderedDict()
        self.running = False
        self.signals_received = 0
        self.trades_executed = 0
        logger.info(f"🎯 A-Bot initialized. Max slots: {self.max_slots}")

    def _fetch_allowed_coins(self):
        self.allowed_coins = []
        for exchange in self.exchanges.values():
            markets = exchange.get_supported_pairs()
            for symbol in markets:
                coin = symbol.base
                if coin not in self.allowed_coins:
                    self.allowed_coins.append(coin.upper())
        self.logger.info(f"Fetched allowed coins from APIs: {self.allowed_coins}")

    def _fetch_default_stake_coin(self):
        # From staking manager's highest APY
        if self.staking_manager:
            self.default_stake_coin = self.staking_manager.get_highest_apy_coin()
        if not self.default_stake_coin:
            self.default_stake_coin = 'ETH'  # Safe fallback
        self.logger.info(f"Fetched default stake coin from API: {self.default_stake_coin}")

    def get_empty_slots(self) -> int:
        return self.max_slots - len(self.positions)

    def handle_signal(self, action: str, coin: str, data: dict = None) -> bool:
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
        if len(self.positions) >= self.max_slots:
            logger.warning(f"⚠️ All {self.max_slots} slots full, cannot buy {coin}")
            return False
        if coin in self.positions:
            logger.warning(f"⚠️ Already holding {coin}, ignoring buy signal")
            return False
        best_exchange, best_price = self._find_best_buy_price(coin)
        if not best_exchange:
            logger.error(f"❌ Could not find exchange to buy {coin}")
            return False
        amount = Decimal('0')  # Orchestrator sets
        logger.info(f"🎯 Executing BUY {coin} on {best_exchange} @ ${best_price}")
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
        if coin not in self.positions:
            logger.warning(f"⚠️ Not holding {coin}, ignoring sell signal")
            return False
        position = self.positions[coin]
        if position['staked'] and self.staking_manager:
            logger.info(f"📤 Unstaking {coin} before sell")
        logger.info(f"🎯 Executing SELL {coin} on {position['exchange']}")
        del self.positions[coin]
        self.trades_executed += 1
        return True

    def _find_best_buy_price(self, coin: str) -> tuple:
        best_exchange = None
        best_price = None
        pair = f"{coin}/USDT"
        for ex_name, exchange in self.exchanges.items():
            try:
                ticker = exchange.get_ticker_price(pair)
                price = ticker.value
                if best_price is None or price < best_price:
                    best_price = price
                    best_exchange = ex_name
                self.logger.info(f"Fetched ticker from API for {ex_name}")
            except Exception as e:
                logger.debug(f"Error fetching {pair} from {ex_name}: {e}")
                continue
        return best_exchange, best_price

    def check_seat_warmers(self, allocated_capital: Decimal) -> None:
        self._fetch_allowed_coins()  # Refresh dynamic
        self._fetch_default_stake_coin()
        empty_slots = self.get_empty_slots()
        if empty_slots > self.seat_warmer_empty_threshold:
            logger.info(f"Chair {empty_slots} empty slots, adding seat warmer")
            self._add_seat_warmer(allocated_capital / self.max_slots)
        elif empty_slots < self.seat_warmer_full_threshold:
            self._remove_oldest_seat_warmer()

    def _add_seat_warmer(self, amount_usd: Decimal) -> bool:
        coin = self.default_stake_coin
        if coin in self.positions:
            for c in self.allowed_coins:
                if c not in self.positions:
                    coin = c
                    break
        if coin in self.positions:
            logger.warning("All target coins already held, cannot add seat warmer")
            return False
        best_exchange, best_price = self._find_best_buy_price(coin)
        if not best_exchange or not best_price:
            return False
        amount = amount_usd / best_price
        logger.info(f"Chair Adding seat warmer: {amount:.6f} {coin} on {best_exchange}")
        self.positions[coin] = {
            'amount': amount,
            'exchange': best_exchange,
            'buy_price': best_price,
            'staked': True,
            'timestamp': datetime.now(),
            'is_seat_warmer': True
        }
        return True

    def _remove_oldest_seat_warmer(self) -> bool:
        for coin, position in self.positions.items():
            if position.get('is_seat_warmer'):
                logger.info(f"Chair Removing oldest seat warmer: {coin}")
                del self.positions[coin]
                return True
        logger.debug("No seat warmers to remove")
        return False

    def stake_idle_funds(self) -> None:
        if not self.staking_manager:
            return
        for coin, position in self.positions.items():
            if not position['staked']:
                logger.info(f"Staking idle {coin}")
                position['staked'] = True

    def liquidate_all(self) -> None:
        logger.info("A-Bot liquidating all positions for mode change")
        for coin in list(self.positions.keys()):
            self._execute_sell(coin)

    def get_status(self) -> Dict:
        return {
            'running': self.running,
            'slots_used': len(self.positions),
            'slots_total': self.max_slots,
            'slots_empty': self.get_empty_slots(),
            'positions': {coin: {'exchange': pos['exchange'], 'staked': pos['staked'], 'is_seat_warmer': pos.get('is_seat_warmer', False)} for coin, pos in self.positions.items()},
            'signals_received': self.signals_received,
            'trades_executed': self.trades_executed,
            'allowed_coins': self.allowed_coins
        }