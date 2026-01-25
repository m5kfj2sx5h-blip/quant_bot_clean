from binance.spot import Spot as BinanceSpot
from decimal import Decimal
from typing import Dict, List, Any, Optional
from domain.entities import Price, Amount, Symbol
from dotenv import load_dotenv
import os

load_dotenv()

class BinanceUSAdapter:
    def __init__(self):
        api_key = os.getenv('BINANCEUS_API_KEY')
        api_secret = os.getenv('BINANCEUS_API_SECRET')
        self.client = BinanceSpot(key=api_key, secret=api_secret, base_url='https://api.binance.us')

    def get_name(self) -> str:
        return "binanceus"

    def get_balance(self, asset: str) -> Decimal:
        balance = self.client.account()['balances']
        for b in balance:
            if b['asset'] == asset.upper():
                return Decimal(b['free'])
        return Decimal('0')

    def get_order_book(self, symbol: Symbol, limit: int = 5) -> Dict[str, List[Dict[str, Decimal]]]:
        book = self.client.depth(str(symbol).replace('/', ''), limit=limit)
        return {
            'bids': [{'price': Decimal(p[0]), 'amount': Decimal(p[1])} for p in book['bids']],
            'asks': [{'price': Decimal(p[0]), 'amount': Decimal(p[1])} for p in book['asks']]
        }

    def get_ticker_price(self, symbol: Symbol) -> Price:
        ticker = self.client.ticker_price(str(symbol).replace('/', ''))
        return Price(Decimal(ticker['price']))

    def place_order(self, symbol: Symbol, side: str, amount: Amount, price: Optional[Price] = None) -> Dict:
        params = {
            'symbol': str(symbol).replace('/', ''),
            'side': side.upper(),
            'type': 'LIMIT' if price else 'MARKET',
            'quantity': str(amount)
        }
        if price:
            params['price'] = str(price)
            params['timeInForce'] = 'GTC'
        return self.client.new_order(**params)

    def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        try:
            self.client.cancel_order(str(symbol).replace('/', ''), orderId=order_id)
            return True
        except:
            return False

    def get_supported_pairs(self) -> List[Symbol]:
        exchange_info = self.client.exchange_info()
        return [Symbol(s['baseAsset'] + '/' + s['quoteAsset']) for s in exchange_info['symbols'] if s['status'] == 'TRADING' and ('USDT' in s['quoteAsset'] or 'USDC' in s['quoteAsset'] or 'USD' in s['quoteAsset'])]