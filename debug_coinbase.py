import asyncio
import logging
from ws import CoinbaseWebSocket, CoinbaseAdvancedWebSocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CoinbaseDiag")

async def test_coinbase():
    print("--- TESTING COINBASE REGULAR ---")
    ws = CoinbaseWebSocket(["BTC-USD"]) # Correct LIST format
    try:
        await ws.connect()
        print("✅ Coinbase Regular Connected")
        # Wait 5s for data
        ws.callbacks.append(lambda x: print(f"Received Regular Data: {x.get('symbol')} {x.get('bids')[0] if x.get('bids') else ''}"))
        await asyncio.sleep(5)
    except Exception as e:
        print(f"❌ Coinbase Regular Failed: {e}")

async def test_coinbase_p():
    print("--- TESTING COINBASE ADVANCED ---")
    ws = CoinbaseAdvancedWebSocket(["BTC-USD"]) # Correct LIST format
    try:
        await ws.connect()
        print("✅ Coinbase Advanced Connected")
        # Wait 5s for data
        ws.callbacks.append(lambda x: print(f"Received Advanced Data: {x.get('symbol')} {x.get('bids')[0] if x.get('bids') else ''}"))
        await asyncio.sleep(5)
    except Exception as e:
        print(f"❌ Coinbase Advanced Failed: {e}")

async def main():
    await test_coinbase()
    await test_coinbase_p()

if __name__ == "__main__":
    asyncio.run(main())
