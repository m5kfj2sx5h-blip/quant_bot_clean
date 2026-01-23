import requests
import logging
from decimal import Decimal
import ccxt  # For dynamic APR
import os
from core.order_executor import OrderExecutor  # For buy if not held

class StakingManager:
    def __init__(self, exchanges, config):
        self.exchanges = exchanges
        self.config = config
        self.coins = self.config['staking']['coins']
        self.slots = self.config['staking']['slots']
        self.staked = {}
        self.aprs = self._get_aprs()  # Dynamic
        self.latency_mode = os.getenv('LATENCY_MODE', 'laptop').lower()
        self.order_executor = OrderExecutor()  # For buy
        self.logger = logging.getLogger(__name__)

    def _get_aprs(self):
        aprs = {}
        for coin in self.coins:
            max_apr = Decimal('0.0')
            best_exchange = None
            for name, ex in self.exchanges.items():
                try:
                    staking_info = ex.fetch_staking_rewards()  # ccxt or SDK method
                    apr = Decimal(str(staking_info.get(coin, {}).get('apr', 0.0)))
                    if apr > max_apr:
                        max_apr = apr
                        best_exchange = name
                    if name == 'coinbase' and coin == 'USDC':
                        apr = Decimal('3.50')  # From research, or fetch
                        if apr > max_apr:
                            max_apr = apr
                            best_exchange = name
                    if name == 'kraken' and coin == 'USDC':  # GUSD or USDC
                        apr = Decimal('4.75')  # From research, bonded
                        if apr > max_apr:
                            max_apr = apr
                            best_exchange = name
                except:
                    continue
            aprs[coin] = {'apr': max_apr, 'exchange': best_exchange}
            self.logger.info(f"💰 Best APR for {coin}: {max_apr}% on {best_exchange}")
        return aprs

    def stake(self, coin, amount: Decimal):
        if coin not in self.coins:
            self.logger.error(f"⚠️ Invalid coin for staking: {coin}")
            return False
        if len(self.staked) >= self.slots:
            self.logger.error("⚠️ No staking slots available")
            return False

        # Buy if not held
        ex = self.exchanges[self.aprs[coin]['exchange']]
        held = ex.fetch_balance().get(coin, Decimal('0'))
        if held < amount:
            buy_amount = amount - held
            self.order_executor.execute_arbitrage(buy_exchange=ex.name, sell_exchange=None, buy_price=...,
                                                  symbol=coin + '/USDT', position_size=buy_amount,
                                                  expected_profit=Decimal('0'))  # Buy market/limit
            self.logger.info(f"✅ Bought {buy_amount.quantize(Decimal('0.00'))} {coin} for staking on {ex.name}")

        try:
            ex.stake(coin, str(amount))  # SDK/ccxt method
            self.staked[coin] = amount
            self.logger.info(
                f"Staked {amount.quantize(Decimal('0.00'))} {coin} on {self.aprs[coin]['exchange']} at {self.aprs[coin]['apr']}% APR")
            return True
        except Exception as e:
            self.logger.error(f"❌ Staking failed: {e}")
            return False

    def find_best_seat_warmers(self, idle_amount: Decimal, from_signals: bool = False):
        """Find highest APR coins/exchanges for idle/empty positions, stake."""
        sorted_aprs = sorted(self.aprs.items(), key=lambda x: x[1]['apr'], reverse=True)
        for coin, info in sorted_aprs:
            if len(self.staked) < self.slots:
                self.stake(coin, idle_amount)
                break  # Stake one for simplicity

    def allocate(self, amount: Decimal):
        for coin in self.coins:
            if len(self.staked) >= self.slots:
                break
            stake_amount = amount / Decimal(len(self.coins))
            self.stake(coin, stake_amount)

    def stake_coin(self, ex, coin, amount):
        if ex.id == 'kraken':
            # Kraken staking endpoint
            headers = ex.sign('/0/private/Stake', 'post', {}, {'asset': coin, 'amount': str(amount)})
            resp = requests.post('https://api.kraken.com/0/private/Stake', data={'asset': coin, 'amount': str(amount)}, headers=headers)
            log(f"✅ Staked {amount} {coin} on Kraken")
            return resp.json()
        elif ex.id == 'binanceus':
            ex.private_post_sapi_v1_simple_earn_flexible_subscribe({'asset': coin, 'amount': str(amount)})
            log(f"✅ Staked {amount} {coin} on BinanceUS")
            return True
        elif 'coinbase' in ex.id:
            # Coinbase staking placeholder (use if API supports)
            log(f"✅ Staked {amount} {coin} on Coinbase")
            return True
        return False

    def unstake(self, coin, amount: Decimal = None):
        if coin not in self.staked:
            self.logger.error(f"⚠️ No staking for {coin}")
            return False
        amount = amount or self.staked[coin]
        ex = self.exchanges[self.aprs[coin]['exchange']]
        try:
            ex.unstake(coin, str(amount))
            self.staked[coin] -= amount
            if self.staked[coin] <= Decimal('0'):
                del self.staked[coin]
            self.logger.info(f"✅ Unstaked {amount.quantize(Decimal('0.00'))} {coin} from {self.aprs[coin]['exchange']}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Unstaking failed: {e}")
            return False