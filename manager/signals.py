#!/usr/bin/env python3
"""
MACRO SIGNAL RECEIVER
Version: 3.0.0
Description: Input for All TradingView Signals

Author: |\/|||
"""

import json
import logging
import hmac
import hashlib
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from apscheduler.schedulers.background import BackgroundScheduler
from decimal import Decimal
from adapters.exchanges.kraken import KrakenAdapter
from adapters.exchanges.wrappers import ExchangeWrapper(ABC):
  # For general if needed

log = logging.getLogger('macro')
SCHED = BackgroundScheduler()

class MacroHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/macro':
            return
        length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(length)
        secret = os.getenv('TV_SECRET')
        if secret:
            sig = hmac.new(secret.encode(), post_data, hashlib.sha256).hexdigest()
            if self.headers.get('X-TV-Signature') != sig:
                return
        try:
            data = json.loads(post_data)
            mode = data.get('mode', 'BTC').upper()
            # forward to server callback
            if hasattr(self.server, 'quant_callback') and callable(self.server.quant_callback):
                self.server.quant_callback(mode)
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        return  # silence default logging

class MacroServer:
    def __init__(self, callback):
        self.callback = callback
        self.latency_mode = os.getenv('LATENCY_MODE', 'laptop').lower()
        self.start_webhook()
        self.start_scheduler()

    def start_webhook(self):
        server = HTTPServer(('0.0.0.0', 8090), MacroHandler)
        server.quant_callback = self.callback
        threading.Thread(target=server.serve_forever, daemon=True).start()
        log.info('📡 Macro webhook listening on :8090/macro')

    def start_scheduler(self):
        # nightly 00:05 book-keeping, adaptive interval for latency
        interval = 300 if self.latency_mode == 'laptop' else 60  # Longer for high latency
        SCHED.add_job(self.gold_sweep, 'interval', seconds=interval)
        SCHED.start()

    def gold_sweep(self):
        kraken = KrakenAdapter()
        try:
            paxg_price = Decimal(str(kraken.book('PAXG-USD')['bids'][0][0]))
        except Exception:
            return
        profit_file = 'logs/cycle_profit.json'
        if not os.path.exists(profit_file):
            return
        try:
            profit = json.load(open(profit_file)).get('profit_usd', Decimal('0'))
            profit = Decimal(str(profit))
        except Exception:
            return
        if profit <= Decimal('0'):
            return
        gold_amt = (profit * Decimal('0.15')) / paxg_price
        cold = os.getenv('COLD_PAXG')
        for ex in ['binance', 'kraken']:
            try:
                exchange = ExchangeWrapper(ABC):

    (ex)  # Revised - use base for general xfer
            exchange.xfer_paxg(gold_amt / Decimal('2'), cold)
            except Exception:
        pass
        json.dump({'profit_usd': Decimal('0')}, open(profit_file, 'w'))
        log.info(f'💰 SWEEP {gold_amt.quantize(Decimal('0.0000'))} PAXG to cold wallet')