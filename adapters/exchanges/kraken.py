from kraken.spot import Spot as KrakenSpot
from decimal import Decimal
from typing import Dict, List, Any, Optional
from domain.entities import Price, Amount, Symbol
from dotenv import load_dotenv
import os

load_dotenv()

class KrakenAdapter:
    def __init__(self):
        api_key = os.getenv('KRAKEN_API_KEY')
        api_secret = os.getenv('KRAKEN_API_SECRET')
        self.client = KrakenSpot(key=api_key, secret=api_secret)

    def get_name(self) -> str:
        return "kraken"

    def get_balance(self, asset: str) -> Decimal:
        balance = self.client.balance()
        return Decimal(balance.get(asset.upper(), '0'))

    def get_order_book(self, symbol: Symbol, limit: int = 5) -> Dict[str, List[Dict[str, Decimal]]]:
        pair = str(symbol).replace('/', '')
        book = self.client.market_depth(pair=pair, count=limit)
        return {
            'bids': [{'price': Decimal(p[0]), 'amount': Decimal(p[1])} for p in book['bids']],
            'asks': [{'price': Decimal(p[0]), 'amount': Decimal(p[1])} for p in book['asks']]
        }

    def get_ticker_price(self, symbol: Symbol) -> Price:
        pair = str(symbol).replace('/', '')
        ticker = self.client.ticker(pair=pair)
        return Price(Decimal(ticker['c'][0]))

    def place_order(self, symbol: Symbol, side: str, amount: Amount, price: Optional[Price] = None) -> Dict:
        pair = str(symbol).replace('/', '')
        order_type = 'limit' if price else 'market'
        return self.client.create_order(pair=pair, type=side.lower(), ordertype=order_type, volume=str(amount), price=str(price) if price else None)

    def cancel_order(self, order_id: str, symbol: Symbol) -> bool:
        try:
            self.client.cancel_order(txid=order_id)
            return True
        except:
            return False

    def get_supported_pairs(self) -> List[Symbol]:
        pairs = self.client.asset_pairs()
        return [Symbol(key.replace('XXBT', 'BTC').replace('XETH', 'ETH').replace('ZUSD', 'USD').replace('.', '/')) for key in pairs]