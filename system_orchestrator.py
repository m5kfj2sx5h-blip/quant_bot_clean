import asyncio
import json
import logging
import os
import signal
import sys
import time
import traceback
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

from adapters.data.feed import DataFeed
from manager.scanner import MarketContext, ArbitrageAnalyzer
from core.order_executor import OrderExecutor
from core.health_monitor import HealthMonitor
from bot.Q import QBot
from bot.A import ABot
from bot.G import GBot
from manager.fee import FeeManager
from manager.money import MoneyManager
from manager.mode import ModeManager
from manager.signals import SignalServer
from manager.staking import StakingManager
from manager.transfer import TransferManager
from utils.logger import get_logger

logger = get_logger(__name__)

class SystemCoordinator:
    def __init__(self):
        self.config = self._load_config()
        self.exchanges = {}
        self.data_feed = None
        self.fee_manager = None
        self.money_manager = None
        self.mode_manager = None
        self.signals_server = None
        self.staking_manager = None
        self.transfer_manager = None
        self.health_monitor = None
        self.running = True

    def _load_config(self) -> Dict[str, Any]:
        with open('config/settings.json', 'r') as f:
            return json.load(f)

    async def initialize(self):
        from adapters.exchanges.binanceus import BinanceUSAdapter
        from adapters.exchanges.kraken import KrakenAdapter
        from adapters.exchanges.coinbase import CoinbaseRegularAdapter
        from adapters.exchanges.coinbase_advanced import CoinbaseAdvancedAdapter
        self.exchanges = {
            'binanceus': BinanceUSAdapter(),
            'kraken': KrakenAdapter(),
            'coinbase': CoinbaseRegularAdapter(),
            'coinbase_advanced': CoinbaseAdvancedAdapter()
        }
        self.data_feed = DataFeed(self.config, logger)
        await self.data_feed.start_websocket_feed()
        self.fee_manager = FeeManager(self.config, self.exchanges)
        self.staking_manager = StakingManager(self.exchanges, self.config)
        self.money_manager = MoneyManager('config/settings.json', self.exchanges, self.staking_manager, self.signals_manager)
        self.mode_manager = ModeManager(None, os.getenv('WEBHOOK_PASSPHRASE'))
        self.signals_server = SignalServer(self.mode_manager.handle_tradingview_signal, None)  # Add ABot callback if needed
        self.signals_server.start()
        self.transfer_manager = TransferManager(self.exchanges, 'USDT', True)
        self.health_monitor = HealthMonitor(None, None)  # Add portfolio/alert

    async def shutdown(self):
        self.running = False
        if self.signals_server:
            self.signals_server.stop()

if __name__ == "__main__":
    coord = SystemCoordinator()
    asyncio.run(coord.initialize())
    # Run bots, etc.