# Config Examples (Reference Only)

These are from original JSONs—not used in code. All dynamic values are fetched from APIs.

## Original coins.json Examples
- Staking coins: ["ADA", "ETH", "SOL", "DOT", "ATOM"]
- ADA: APY 4.6, unbond_days 5, exchanges: ["binance", "kraken"]
- ETH: APY 4.2, unbond_days 0, exchanges: ["kraken", "coinbase"]
- SOL: APY 7.2, unbond_days 2, exchanges: ["binance", "kraken", "coinbase"]

## Original settings.json Examples
- Total capital: 10000 USD
- Allocations: BTC mode - QBot 85%, ABot 15%; Gold mode - QBot 15%, GBot 85%
- Risk: max_trade_usd 500, min_spread_pct 0.08
- Fees: Binance 0.001 (BNB rebate), Kraken 0.0000 (free $10k/month), Coinbase 0.0000 (free $500/month)
- Networks: ["TRC20", "SOL", "BNB", "ERC20", "AVALANCHE", "OPTIMISM"]