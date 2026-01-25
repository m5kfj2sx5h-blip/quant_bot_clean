import logging
from decimal import Decimal
from typing import Dict
from datetime import datetime
from manager.conversion import ConversionManager
from manager.mode import ModeManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MoneyManager:
    def __init__(self, config_path='config/rebalance_config.json', exchanges: Dict = None, staking_manager=None, signals_manager=None):
        self.config_path = config_path
        self.exchanges = exchanges
        self.staking_manager = staking_manager
        self.signals_manager = signals_manager
        self.drift_threshold = Decimal('0.15')
        self.conversion_manager = ConversionManager()
        self.mode_manager = ModeManager()
        self.capital_mode = "balanced"
        self._cache = {}
        self.cache_ttl = 300  # 5 min
        self.retry_count = 3
        self._load_config()
        logger.info(f"⚖️ MONEY MANAGER Initialized")

    def _load_config(self):
        pass  # No ops values

    def generate_macro_plan(self, price_data, min_btc_reserve, min_stable_reserve):
        balances = self._fetch_balances()
        total_values = {}
        total_portfolio_value = Decimal('0.0')
        for ex_name, balance in balances.items():
            for currency, amount in balance.items():
                if amount <= Decimal('0'):
                    continue
                if currency in ['USDT', 'USDC', 'USD']:
                    value = amount
                    total_values[currency] = total_values.get(currency, Decimal('0.0')) + value
                    total_portfolio_value += value
                elif currency == 'BTC':
                    btc_value = self._get_btc_value_for_exchange(ex_name, amount, price_data)
                    if btc_value > Decimal('0'):
                        total_values['BTC'] = total_values.get('BTC', Decimal('0.0')) + btc_value
                        total_portfolio_value += btc_value
        if total_portfolio_value <= Decimal('0'):
            return None
        current_allocations = {asset: value / total_portfolio_value for asset, value in total_values.items()}
        total_stable = sum(total_values.get(c, Decimal('0.0')) for c in ['USDT', 'USDC', 'USD'])
        self.capital_mode = "bottlenecked" if total_stable < Decimal('1500') else "balanced"
        logger.info(f"Capital mode: {self.capital_mode.upper()} (stable: ${total_stable:.2f})")
        current_mode = self.mode_manager.get_current_mode()
        if current_mode == 'BTC':
            arb_pct = Decimal('0.85')
            staking_pct = Decimal('0.15')
            hedging_pct = Decimal('0.0')
        else:
            arb_pct = Decimal('0.15')
            staking_pct = Decimal('0.0')
            hedging_pct = Decimal('0.85')
        logger.info(f"Capital allotment ({current_mode}): Arb {arb_pct * 100}%, Staking {staking_pct * 100}%, Hedging {hedging_pct * 100}%")
        target_btc = total_portfolio_value * (arb_pct + hedging_pct)
        target_stable = total_portfolio_value * staking_pct
        drift_data = []
        for asset, current in current_allocations.items():
            deviation = abs(current - Decimal('0.5') if asset == 'BTC' else Decimal('0.25'))  # Dynamic targets from analysis
            if deviation >= Decimal('0.15'):
                drift_data.append((asset, deviation))
        if drift_data:
            if self.conversion_manager.control_drift(drift_data):
                self.logger.info(f"Drift controlled via intra-triangular for {len(drift_data)} assets — no transfer fees")
            else:
                self.logger.warning(f"Drift >=15% for {len(drift_data)} assets — no intra route, manual transfer needed")
        if any(dev >= Decimal('0.15') for _, dev in drift_data) or total_stable < Decimal('1500'):
            self.capital_mode = "bottlenecked"
        else:
            self.capital_mode = "balanced"
        self.logger.info(f"Capital mode: {self.capital_mode}")
        return {}  # Plan dict if needed

    def _fetch_balances(self) -> Dict:
        cache_key = 'balances'
        if cache_key in self._cache and time.time() - self._cache[cache_key]['timestamp'] < self.cache_ttl:
            return self._cache[cache_key]['data']
        balances = {}
        for ex_name, exchange in self.exchanges.items():
            for attempt in range(self.retry_count):
                try:
                    balances[ex_name] = exchange.get_balance()
                    self.logger.info(f"Fetched balances from API for {ex_name}")
                    break
                except Exception as e:
                    logger.warning(f"Balance fetch attempt {attempt+1} failed for {ex_name}: {e}")
                    if attempt == self.retry_count - 1:
                        raise Exception(f"Failed to fetch balances for {ex_name}")
                    time.sleep(1)
        self._cache[cache_key] = {'data': balances, 'timestamp': time.time()}
        return balances

    def _get_btc_value_for_exchange(self, exchange_name, btc_amount, price_data):
        try:
            btc_pairs = ['BTC/USDT', 'BTC/USDC', 'BTC/USD']
            for pair in btc_pairs:
                if pair in price_data and exchange_name in price_data[pair]:
                    price_info = price_data[pair][exchange_name]
                    if 'bid' in price_info and price_info['bid']:
                        return Decimal(str(btc_amount)) * Decimal(str(price_info['bid']))
            for pair, exchanges in price_data.items():
                if 'BTC' in pair and exchange_name in exchanges:
                    price_info = exchanges[exchange_name]
                    if 'bid' in price_info and price_info['bid']:
                        return Decimal(str(btc_amount)) * Decimal(str(price_info['bid']))
        except Exception as e:
            logger.error(f"Error fetching BTC value for {exchange_name}: {e}")
        return Decimal('0.0')