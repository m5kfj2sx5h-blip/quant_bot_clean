import logging
from decimal import Decimal
from typing import Dict
from dotenv import load_dotenv
import time

load_dotenv()

logger = logging.getLogger(__name__)

class StakingManager:
    def __init__(self, exchanges, config):
        self.exchanges = exchanges
        self.config = config
        self.min_apr = self.config.get('staking', {}).get('min_apr', Decimal('1.0'))
        self.min_rank = self.config.get('staking', {}).get('min_rank', 100)
        self.min_bond_short = self.config.get('staking', {}).get('min_bond_short', Decimal('7'))
        self.min_bond_long = self.config.get('staking', {}).get('min_bond_long', Decimal('7'))
        self.slots = self.config.get('staking', {}).get('slots', 6)
        self.staked = {}
        self.aprs = {}
        self._cache = {}
        self.cache_ttl = config.get('cache_ttl_minutes', 5) * 60
        self.retry_count = config.get('retry_count', 3)
        self._fetch_aprs()

    def _fetch_aprs(self):
        cache_key = 'staking_aprs'
        if cache_key in self._cache and time.time() - self._cache[cache_key]['timestamp'] < self.cache_ttl:
            self.aprs = self._cache[cache_key]['data']
            return
        self.aprs = {}
        for name, exchange in self.exchanges.items():
            for attempt in range(self.retry_count):
                try:
                    staking_assets = exchange.client.get_staking_assets() if hasattr(exchange.client, 'get_staking_assets') else []
                    for asset in staking_assets:
                        coin = asset.get('symbol')
                        apr = Decimal(str(asset.get('apr', 0.0)))
                        bond_days = Decimal(str(asset.get('bond_period_days', 0)))
                        if apr < self.min_apr:
                            continue
                        self.aprs[coin] = {'apr': apr, 'bond_days': bond_days, 'exchange': name}
                        logger.info(f"Fetched staking rewards from API for {coin} on {name}")
                    break
                except Exception as e:
                    logger.warning(f"Staking fetch attempt {attempt+1} failed for {name}: {e}")
                    if attempt == self.retry_count - 1:
                        raise Exception(f"Failed to fetch staking for {name}")
                    time.sleep(1)
        self._cache[cache_key] = {'data': self.aprs, 'timestamp': time.time()}

    def stake(self, coin, amount: Decimal):
        if coin not in self.aprs:
            logger.error(f"Warning: Invalid coin for staking: {coin}")
            return False
        if len(self.staked) >= self.slots:
            logger.error("Warning: No staking slots available")
            return False
        ex = self.exchanges[self.aprs[coin]['exchange']]
        held = ex.get_balance(coin)
        if held < amount:
            buy_amount = amount - held
            ex.place_order(coin + '/USDT', 'buy', buy_amount)
            logger.info(f"Money: Bought {buy_amount.quantize(Decimal('0.00'))} {coin} for staking on {ex.get_name()}")
        try:
            ex.client.stake(coin, str(amount))
            self.staked[coin] = amount
            logger.info(f"Checkmark: Staked {amount.quantize(Decimal('0.00'))} {coin} on {self.aprs[coin]['exchange']} at {self.aprs[coin]['apr']}% APR (bond: {self.aprs[coin]['bond_days']} days)")
            return True
        except Exception as e:
            logger.error(f"Cross: Staking failed: {e}")
            return False

    def get_highest_apy_coin(self) -> str:
        if not self.aprs:
            return 'ETH'  # Fallback
        return max(self.aprs, key=lambda x: self.aprs[x]['apr'])

    def find_best_seat_warmers(self, idle_amount: Decimal, high_idle: bool = False):
        self._fetch_aprs()  # Refresh
        sorted_aprs = sorted(self.aprs.items(), key=lambda x: x[1]['apr'], reverse=True)
        stake_count = self.slots - len(self.staked)
        if stake_count <= 0:
            return
        per_stake = idle_amount / Decimal(stake_count)
        for coin, info in sorted_aprs:
            if len(self.staked) < self.slots:
                if high_idle:
                    if info['bond_days'] > self.min_bond_long:
                        self.stake(coin, per_stake)
                else:
                    if info['bond_days'] < self.min_bond_short:
                        self.stake(coin, per_stake)

    def allocate(self, amount: Decimal):
        self._fetch_aprs()
        sorted_aprs = sorted(self.aprs.items(), key=lambda x: x[1]['apr'], reverse=True)[:len(self.aprs)]  # All that meet min_apr
        for coin, _ in sorted_aprs:
            if len(self.staked) >= self.slots:
                break
            stake_amount = amount / Decimal(len(sorted_aprs))
            self.stake(coin, stake_amount)

    def unstake(self, coin, amount: Decimal = None):
        if coin not in self.staked:
            logger.error(f"Warning: No staking for {coin}")
            return False
        amount = amount or self.staked[coin]
        ex = self.exchanges[self.aprs[coin]['exchange']]
        try:
            ex.client.unstake(coin, str(amount))
            self.staked[coin] -= amount
            if self.staked[coin] <= Decimal('0'):
                del self.staked[coin]
            logger.info(f"Checkmark: Unstaked {amount.quantize(Decimal('0.00'))} {coin} from {self.aprs[coin]['exchange']}")
            ex.place_order(coin + '/USDT', 'sell', amount)
            return True
        except Exception as e:
            logger.error(f"Cross: Unstaking failed: {e}")
            return False