import ccxt.async_support as ccxt
import base64
import re
import logging
from ecdsa import SigningKey
from ecdsa.util import sigencode_der
from decimal import Decimal
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CoinbaseAdvancedAdapter:
    """Adapter for Coinbase Advanced Trade API"""
    
    @staticmethod
    def _parse_pem_key(pem_key: str) -> bytes:
        try:
            pem_key = pem_key.strip()
            if '-----BEGIN PRIVATE KEY-----' in pem_key:
                b64_key = re.search(r'-----BEGIN PRIVATE KEY-----(.*?)-----END PRIVATE KEY-----', pem_key, re.DOTALL)
                if b64_key:
                    key_data = b64_key.group(1).replace('\n', '')
                else:
                    raise ValueError("Invalid PEM format")
            elif '-----BEGIN EC PRIVATE KEY-----' in pem_key:
                b64_key = re.search(r'-----BEGIN EC PRIVATE KEY-----(.*?)-----END EC PRIVATE KEY-----', pem_key, re.DOTALL)
                if b64_key:
                    key_data = b64_key.group(1).replace('\n', '').replace(' ', '')
                else:
                    raise ValueError("Invalid EC PEM format")
            else:
                key_data = pem_key.replace('\n', '')
            key_bytes = base64.b64decode(key_data)
            try:
                key = SigningKey.from_der(key_bytes)
                return key.to_der()
            except:
                return key_bytes
        except Exception as e:
            logger.error(f"Error parsing PEM key: {e}")
            return b''

    def __init__(self, config: Dict[str, Any]):
        parsed_secret = self._parse_pem_key(config.get('api_secret', ''))
        self.client = ccxt.coinbaseadvanced({
            'apiKey': config.get('api_key', ''),
            'secret': base64.b64encode(parsed_secret).decode() if parsed_secret else config.get('api_secret', ''),
            'enableRateLimit': True
        })
        self.name = "coinbase_advanced"

    def get_name(self) -> str:
        return self.name

    async def get_balance(self, asset: str) -> Decimal:
        balance = await self.client.fetch_balance()
        return Decimal(str(balance.get(asset.upper(), {}).get('free', '0')))

    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict[str, List[Dict[str, Decimal]]]:
        book = await self.client.fetch_order_book(symbol.replace('/', '-'), limit)
        return {
            'bids': [{'price': Decimal(str(p[0])), 'amount': Decimal(str(p[1]))} for p in book['bids']],
            'asks': [{'price': Decimal(str(p[0])), 'amount': Decimal(str(p[1]))} for p in book['asks']]
        }

    async def get_ticker_price(self, symbol: str) -> Decimal:
        ticker = await self.client.fetch_ticker(symbol.replace('/', '-'))
        return Decimal(str(ticker['last']))

    async def place_order(self, symbol: str, side: str, amount: Decimal, price: Optional[Decimal] = None) -> Dict:
        order_type = 'limit' if price else 'market'
        return await self.client.create_order(
            symbol.replace('/', '-'), 
            order_type, 
            side, 
            float(amount), 
            float(price) if price else None
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self.client.cancel_order(order_id, symbol.replace('/', '-'))
            return True
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False

    def get_supported_pairs(self) -> List[str]:
        markets = self.client.load_markets()
        return [pair.replace('-', '/') for pair in markets if 'USDT' in pair or 'USDC' in pair or 'USD' in pair]
