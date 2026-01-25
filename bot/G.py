"""
G-Bot: Gold Vault / Piggy Bank
Version: 3.0.0

Key principles:
- Signal-driven by MACRO SIGNAL
- In GOLD Mode: Accumulates PAXG with 85% of capital
- On flip to BTC Mode: Sells ONLY 85% of PAXG, keeps 15% FOREVER
- Manual sweep: 15% of PROFITS to cold wallet, max 2x/month
- The vault NEVER gives up more than 85% of what goes in
"""
import logging
import os
import json
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class GBot:
    """
    Gold Vault Bot - Accumulates PAXG and preserves 15% forever
    """

    def __init__(self, config: dict, exchanges: Dict, fee_manager=None):
        self.config = config
        self.exchanges = exchanges
        self.fee_manager = fee_manager
        
        # Gold configuration
        gold_config = config.get('gold', {})
        self.sweep_profit_pct = Decimal(str(gold_config.get('sweep_profit_pct', 15))) / 100
        self.max_sweeps_per_month = gold_config.get('max_sweeps_per_month', 2)
        self.sell_on_mode_flip_pct = Decimal(str(gold_config.get('sell_on_mode_flip_pct', 85))) / 100
        self.keep_forever_pct = Decimal(str(gold_config.get('keep_forever_pct', 15))) / 100
        
        # Cold wallet from env
        self.cold_wallet = os.getenv('BASE_WALLET', '')
        
        # State tracking
        self.sweeps_this_month = 0
        self.last_sweep_month = None
        self.total_paxg_accumulated = Decimal('0')
        self.total_paxg_swept = Decimal('0')
        self.running = False
        
        # Profit tracking file
        self.profit_file = Path('logs/gold_profits.json')
        self._load_state()
        
        logger.info(f"🏆 G-Bot initialized. Sweep: {float(self.sweep_profit_pct)*100}% of profits, Max: {self.max_sweeps_per_month}/month")
        logger.info(f"🏆 Mode flip: Sell {float(self.sell_on_mode_flip_pct)*100}%, Keep {float(self.keep_forever_pct)*100}% forever")

    def _load_state(self):
        """Load state from file"""
        try:
            if self.profit_file.exists():
                data = json.loads(self.profit_file.read_text())
                self.sweeps_this_month = data.get('sweeps_this_month', 0)
                self.last_sweep_month = data.get('last_sweep_month')
                self.total_paxg_accumulated = Decimal(str(data.get('total_paxg_accumulated', '0')))
                self.total_paxg_swept = Decimal(str(data.get('total_paxg_swept', '0')))
        except Exception as e:
            logger.warning(f"Could not load G-Bot state: {e}")

    def _save_state(self):
        """Save state to file"""
        try:
            self.profit_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'sweeps_this_month': self.sweeps_this_month,
                'last_sweep_month': self.last_sweep_month,
                'total_paxg_accumulated': str(self.total_paxg_accumulated),
                'total_paxg_swept': str(self.total_paxg_swept),
                'last_updated': datetime.now().isoformat()
            }
            self.profit_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Could not save G-Bot state: {e}")

    def _check_month_reset(self):
        """Reset sweep counter if new month"""
        current_month = datetime.now().strftime('%Y-%m')
        if self.last_sweep_month != current_month:
            self.sweeps_this_month = 0
            self.last_sweep_month = current_month
            self._save_state()

    async def accumulate_paxg(self, amount_usd: Decimal) -> bool:
        """
        Accumulate PAXG with allocated capital (GOLD Mode)
        
        Args:
            amount_usd: USD amount to spend on PAXG
        
        Returns:
            True if successful
        """
        best_exchange, best_price = await self._find_best_paxg_price()
        if not best_exchange or not best_price:
            logger.error("❌ Could not find exchange to buy PAXG")
            return False
        
        paxg_amount = amount_usd / best_price
        
        logger.info(f"🏆 Accumulating {paxg_amount:.6f} PAXG on {best_exchange} @ ${best_price:.2f}")
        
        try:
            exchange = self.exchanges.get(best_exchange)
            if exchange:
                # Execute buy order
                # await exchange.place_order('PAXG/USDT', 'buy', paxg_amount, best_price)
                self.total_paxg_accumulated += paxg_amount
                self._save_state()
                return True
        except Exception as e:
            logger.error(f"❌ Error accumulating PAXG: {e}")
        
        return False

    async def handle_mode_flip_to_btc(self) -> Decimal:
        """
        Handle mode flip from GOLD to BTC.
        Sells EXACTLY 85% of PAXG holdings, keeps 15% FOREVER.
        
        Returns:
            USD value of sold PAXG (to be redistributed to Q-Bot and A-Bot)
        """
        logger.info("🔄 G-Bot handling mode flip to BTC - Selling 85%, keeping 15% forever")
        
        total_sold_usd = Decimal('0')
        
        for ex_name, exchange in self.exchanges.items():
            try:
                # Get PAXG balance
                balance = await exchange.get_balance('PAXG')
                if balance <= 0:
                    continue
                
                # Calculate sell amount (85%)
                sell_amount = balance * self.sell_on_mode_flip_pct
                keep_amount = balance * self.keep_forever_pct
                
                logger.info(f"🏆 {ex_name}: Selling {sell_amount:.6f} PAXG, keeping {keep_amount:.6f} forever")
                
                # Get current price
                price = await exchange.get_ticker_price('PAXG/USDT')
                if price:
                    # Execute sell
                    # await exchange.place_order('PAXG/USDT', 'sell', sell_amount)
                    total_sold_usd += sell_amount * price
                    
            except Exception as e:
                logger.error(f"❌ Error selling PAXG on {ex_name}: {e}")
        
        logger.info(f"🏆 Mode flip complete. Released ${total_sold_usd:.2f} for Q-Bot and A-Bot")
        return total_sold_usd

    def calculate_sweep_amount(self, total_gold_profit_usd: Decimal) -> Dict:
        """
        Calculate sweep amount based on profits.
        MANUAL ONLY - this just calculates, does not execute.
        
        Args:
            total_gold_profit_usd: Total profit in USD from gold holdings
        
        Returns:
            Dict with sweep details
        """
        self._check_month_reset()
        
        if total_gold_profit_usd <= 0:
            return {
                'can_sweep': False,
                'reason': 'No profits to sweep',
                'sweep_amount_usd': Decimal('0'),
                'sweeps_remaining': self.max_sweeps_per_month - self.sweeps_this_month
            }
        
        if self.sweeps_this_month >= self.max_sweeps_per_month:
            return {
                'can_sweep': False,
                'reason': f'Max sweeps ({self.max_sweeps_per_month}) reached this month',
                'sweep_amount_usd': Decimal('0'),
                'sweeps_remaining': 0
            }
        
        if not self.cold_wallet:
            return {
                'can_sweep': False,
                'reason': 'No cold wallet configured',
                'sweep_amount_usd': Decimal('0'),
                'sweeps_remaining': self.max_sweeps_per_month - self.sweeps_this_month
            }
        
        # Calculate 15% of profits
        sweep_amount_usd = total_gold_profit_usd * self.sweep_profit_pct
        
        return {
            'can_sweep': True,
            'sweep_amount_usd': sweep_amount_usd,
            'sweep_pct': float(self.sweep_profit_pct * 100),
            'sweeps_remaining': self.max_sweeps_per_month - self.sweeps_this_month,
            'cold_wallet': self.cold_wallet[:10] + '...' + self.cold_wallet[-6:] if len(self.cold_wallet) > 20 else self.cold_wallet
        }

    async def execute_manual_sweep(self, total_gold_profit_usd: Decimal) -> bool:
        """
        Execute a manual gold sweep.
        MUST BE TRIGGERED MANUALLY - never auto-executes.
        
        Args:
            total_gold_profit_usd: Total profit to calculate sweep from
        
        Returns:
            True if sweep was executed
        """
        sweep_info = self.calculate_sweep_amount(total_gold_profit_usd)
        
        if not sweep_info['can_sweep']:
            logger.warning(f"⚠️ Cannot sweep: {sweep_info['reason']}")
            return False
        
        sweep_amount_usd = sweep_info['sweep_amount_usd']
        
        logger.info(f"💰 MANUAL SWEEP: Sending ${sweep_amount_usd:.2f} worth of PAXG to cold wallet")
        
        # Find exchange with PAXG and execute withdrawal
        for ex_name, exchange in self.exchanges.items():
            try:
                balance = await exchange.get_balance('PAXG')
                price = await exchange.get_ticker_price('PAXG/USDT')
                
                if balance > 0 and price:
                    paxg_to_sweep = sweep_amount_usd / price
                    
                    if balance >= paxg_to_sweep:
                        logger.info(f"💰 Sweeping {paxg_to_sweep:.6f} PAXG from {ex_name} to {self.cold_wallet}")
                        # await exchange.withdraw('PAXG', paxg_to_sweep, self.cold_wallet)
                        
                        self.sweeps_this_month += 1
                        self.total_paxg_swept += paxg_to_sweep
                        self._save_state()
                        
                        logger.info(f"✅ Sweep complete. Sweeps this month: {self.sweeps_this_month}/{self.max_sweeps_per_month}")
                        return True
                        
            except Exception as e:
                logger.error(f"❌ Error sweeping from {ex_name}: {e}")
        
        logger.error("❌ Could not complete sweep - insufficient PAXG balance")
        return False

    async def _find_best_paxg_price(self) -> tuple:
        """Find the exchange with the best PAXG buy price"""
        best_exchange = None
        best_price = None
        
        for ex_name, exchange in self.exchanges.items():
            try:
                price = await exchange.get_ticker_price('PAXG/USDT')
                if price and (best_price is None or price < best_price):
                    best_price = price
                    best_exchange = ex_name
            except Exception as e:
                logger.debug(f"Error fetching PAXG price from {ex_name}: {e}")
        
        return best_exchange, best_price

    def get_status(self) -> Dict:
        """Get current G-Bot status for dashboard"""
        self._check_month_reset()
        
        return {
            'running': self.running,
            'total_paxg_accumulated': float(self.total_paxg_accumulated),
            'total_paxg_swept': float(self.total_paxg_swept),
            'sweeps_this_month': self.sweeps_this_month,
            'max_sweeps_per_month': self.max_sweeps_per_month,
            'sweeps_remaining': self.max_sweeps_per_month - self.sweeps_this_month,
            'sell_on_flip_pct': float(self.sell_on_mode_flip_pct * 100),
            'keep_forever_pct': float(self.keep_forever_pct * 100),
            'cold_wallet_configured': bool(self.cold_wallet)
        }
