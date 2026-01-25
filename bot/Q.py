import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class QBot:
    def __init__(self, config: dict, exchanges: Dict, fee_manager=None, threshold_manager=None, health_monitor=None):
        self.config = config
        self.exchanges = exchanges
        self.fee_manager = fee_manager
        self.threshold_manager = threshold_manager
        self.health_monitor = health_monitor
        qbot_split = config.get('capital', {}).get('qbot_internal_split', {})
        self.cross_exchange_pct = Decimal(str(qbot_split.get('cross_exchange', 80))) / 100
        self.triangular_pct = Decimal(str(qbot_split.get('triangular', 20))) / 100
        self.pairs = []  # Dynamic
        risk_config = config.get('risk', {})
        self.max_trade_usd = Decimal(str(risk_config.get('max_trade_usd', 500)))
        self.min_spread_pct = Decimal(str(risk_config.get('min_spread_pct', 0.08))) / 100
        self.depth_multiplier = Decimal(str(risk_config.get('depth_multiplier_min', 2.5)))
        cycle_config = config.get('cycle_times', {})
        self.cross_exchange_cycle = cycle_config.get('qbot_cross_exchange_sec', 10)
        self.triangular_cycle = cycle_config.get('qbot_triangular_sec', 30)
        self.running = False
        self.last_cross_exchange_scan = None
        self.last_triangular_scan = None
        self.opportunities_found = 0
        self.trades_executed = 0
        logger.info(f"Q-Bot initialized. Split: {float(self.cross_exchange_pct)*100}% cross-ex / {float(self.triangular_pct)*100}% triangular")

    def _fetch_pairs(self):
        self.pairs = []
        for exchange in self.exchanges.values():
            markets = exchange.get_supported_pairs()
            for symbol in markets:
                pair = str(symbol)
                if pair not in self.pairs:
                    self.pairs.append(pair)
        self.logger.info(f"Fetched arbitrage pairs from APIs: {self.pairs}")

    def get_profit_threshold(self) -> Decimal:
        if self.threshold_manager:
            return self.threshold_manager.get_threshold()
        return Decimal(str(self.config.get('thresholds', {}).get('baseline_profit_pct', 0.5))) / 100

    def get_effective_fee(self, exchange: str, trade_value: Decimal) -> Decimal:
        if self.fee_manager:
            return self.fee_manager.get_effective_fee(exchange, trade_value)
        ex_config = self.config.get('exchanges', {}).get(exchange, {})
        return Decimal(str(ex_config.get('taker_fee', 0.001)))

    async def scan_cross_exchange(self, allocated_capital: Dict[str, Decimal]) -> List[Dict]:
        self._fetch_pairs()  # Refresh dynamic
        opportunities = []
        threshold = self.get_profit_threshold()
        for pair in self.pairs:
            prices = {}
            books = {}
            for ex_name, exchange in self.exchanges.items():
                try:
                    book = exchange.get_order_book(pair)
                    if book and book.get('bids') and book.get('asks'):
                        prices[ex_name] = {
                            'bid': book['bids'][0]['price'],
                            'ask': book['asks'][0]['price'],
                            'bid_vol': book['bids'][0]['amount'],
                            'ask_vol': book['asks'][0]['amount']
                        }
                        books[ex_name] = book
                    self.logger.info(f"Fetched order book from API for {ex_name}")
                except Exception as e:
                    logger.debug(f"Error fetching {pair} from {ex_name}: {e}")
                    continue
            for buy_ex in prices:
                for sell_ex in prices:
                    if buy_ex == sell_ex:
                        continue
                    buy_price = prices[buy_ex]['ask']
                    sell_price = prices[sell_ex]['bid']
                    if buy_price <= 0:
                        continue
                    spread = (sell_price - buy_price) / buy_price
                    trade_value = min(allocated_capital.get(buy_ex, Decimal('0')), allocated_capital.get(sell_ex, Decimal('0')), self.max_trade_usd)
                    if trade_value <= 0:
                        continue
                    buy_fee = self.get_effective_fee(buy_ex, trade_value)
                    sell_fee = self.get_effective_fee(sell_ex, trade_value)
                    total_fees = buy_fee + sell_fee
                    net_profit = spread - total_fees
                    if net_profit >= threshold:
                        buy_depth = prices[buy_ex]['ask_vol'] * buy_price
                        sell_depth = prices[sell_ex]['bid_vol'] * sell_price
                        if buy_depth >= trade_value * self.depth_multiplier and sell_depth >= trade_value * self.depth_multiplier:
                            opportunities.append({
                                'type': 'cross_exchange',
                                'pair': pair,
                                'buy_exchange': buy_ex,
                                'sell_exchange': sell_ex,
                                'buy_price': buy_price,
                                'sell_price': sell_price,
                                'spread_pct': float(spread * 100),
                                'net_profit_pct': float(net_profit * 100),
                                'trade_value': trade_value,
                                'timestamp': datetime.now()
                            })
                            self.opportunities_found += 1
                            logger.info(f"Cross-Ex opportunity: {pair} Buy@{buy_ex} ${buy_price:.2f} → Sell@{sell_ex} ${sell_price:.2f} = {net_profit*100:.3f}%")
        return opportunities

    async def scan_triangular(self, exchange_name: str, capital: Decimal) -> List[Dict]:
        opportunities = []
        threshold = self.get_profit_threshold()
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return opportunities
        triangular_paths = [  # Dynamic if needed
            ['BTC/USDT', 'ETH/BTC', 'ETH/USDT'],
            ['BTC/USDC', 'ETH/BTC', 'ETH/USDC'],
            ['BTC/USDT', 'SOL/BTC', 'SOL/USDT'],
            ['ETH/USDT', 'SOL/ETH', 'SOL/USDT'],
        ]
        for path in triangular_paths:
            try:
                books = []
                for pair in path:
                    book = exchange.get_order_book(pair)
                    if not book or not book.get('bids') or not book.get('asks'):
                        break
                    books.append(book)
                if len(books) != 3:
                    continue
                ask1 = books[0]['asks'][0]['price']
                bid2 = books[1]['bids'][0]['price']
                bid3 = books[2]['bids'][0]['price']
                if ask1 <= 0:
                    continue
                profit = (Decimal('1') / ask1) * bid2 * bid3 - Decimal('1')
                trade_value = min(capital, self.max_trade_usd)
                fee_per_trade = self.get_effective_fee(exchange_name, trade_value)
                total_fees = fee_per_trade * 3
                net_profit = profit - total_fees
                if net_profit >= threshold:
                    opportunities.append({
                        'type': 'triangular',
                        'exchange': exchange_name,
                        'path': path,
                        'gross_profit_pct': float(profit * 100),
                        'net_profit_pct': float(net_profit * 100),
                        'trade_value': trade_value,
                        'timestamp': datetime.now()
                    })
                    self.opportunities_found += 1
                    logger.info(f"Triangular opportunity on {exchange_name}: {' → '.join(path)} = {net_profit*100:.3f}%")
            except Exception as e:
                logger.debug(f"Error scanning triangular path {path} on {exchange_name}: {e}")
                continue
        return opportunities

    async def execute_cross_exchange(self, opportunity: Dict) -> bool:
        try:
            pair = opportunity['pair']
            buy_ex = self.exchanges.get(opportunity['buy_exchange'])
            sell_ex = self.exchanges.get(opportunity['sell_exchange'])
            if not buy_ex or not sell_ex:
                return False
            trade_value = opportunity['trade_value']
            buy_price = opportunity['buy_price']
            amount = trade_value / buy_price
            logger.info(f"Executing cross-ex: BUY {amount:.6f} {pair} @ {opportunity['buy_exchange']}")
            buy_order = buy_ex.place_order(pair, 'buy', amount, buy_price)
            logger.info(f"Executing cross-ex: SELL {amount:.6f} {pair} @ {opportunity['sell_exchange']}")
            sell_order = sell_ex.place_order(pair, 'sell', amount, opportunity['sell_price'])
            self.trades_executed += 1
            return True
        except Exception as e:
            logger.error(f"Error executing cross-exchange trade: {e}")
            return False

    async def execute_triangular(self, opportunity: Dict) -> bool:
        try:
            exchange = self.exchanges.get(opportunity['exchange'])
            if not exchange:
                return False
            path = opportunity['path']
            trade_value = opportunity['trade_value']
            logger.info(f"Executing triangular on {opportunity['exchange']}: {' → '.join(path)}")
            for i, pair in enumerate(path):
                book = exchange.get_order_book(pair)
                if i == 0:
                    price = book['asks'][0]['price']
                    amount = trade_value / price
                    exchange.place_order(pair, 'buy', amount, price)
                else:
                    price = book['bids'][0]['price']
                    exchange.place_order(pair, 'sell', amount, price)
            self.trades_executed += 1
            return True
        except Exception as e:
            logger.error(f"Error executing triangular trade: {e}")
            return False

    def get_status(self) -> Dict:
        return {
            'running': self.running,
            'opportunities_found': self.opportunities_found,
            'trades_executed': self.trades_executed,
            'last_cross_exchange_scan': self.last_cross_exchange_scan,
            'last_triangular_scan': self.last_triangular_scan,
            'cross_exchange_cycle_sec': self.cross_exchange_cycle,
            'triangular_cycle_sec': self.triangular_cycle,
            'profit_threshold_pct': float(self.get_profit_threshold() * 100)
        }