Improvements:

## 1. Why small accounts usually lose

For small capital, the default spatial arbitrage (buy on Exchange A, withdraw, deposit to B, sell) is almost always negative after **all** costs.

Key reasons:

- Trading fees: Typical spot taker fees are around 0.1–0.25% per side, so a round trip is 0.2–0.5%.
- Withdrawal / network fees: A single withdrawal can easily be a flat 10–50 USD equivalent on major chains during congestion.
- Slippage: Even “liquid” books often add 0.05–0.15% extra cost when you cross the spread and walk the book.
- Small spreads: On big coins between big CEXs, typical price gaps are far below 0.5% except during short spikes, so after 0.3–0.7% all‑in costs there is little or no edge.

Concrete example for a $2,000 account:

- Spread between Binance and Coinbase on BTC: 0.25%.
- Spot taker fee each side 0.1% (0.2% total), plus fixed 10–20 USD withdrawal fee.
- Gross edge 0.25% of $2,000 = $5; one on‑chain withdrawal can cost more than $5 alone.

Conclusion: as long as you **move coins on‑chain per trade**, a truly small account is structurally dead in the water.

***

## 2. Small‑account‑friendly arbitrage patterns

To make a small account work, you must select setups where **fixed fees are negligible and you mostly pay percentage fees**.

The patterns that fit:

1. **Same‑exchange triangular arbitrage**  
   - You trade three markets on one exchange, e.g. USDT → BTC → ETH → USDT.
   - No withdrawals, only trading fees (e.g. 0.1% × 3 = 0.3% round trip).
   - Viable if your detected spread is comfortably above ~3× your per‑trade fee (e.g. require >0.35–0.4% if each leg is 0.1%).

2. **Intra‑exchange micro‑spreads on long‑tail pairs**  
   - On smaller/alt pairs, spreads can be >0.5–1.0%, even when main pairs are tight.
   - With a small account, your trades are tiny relative to book depth, so you can sometimes capture that spread with limit‑order placement instead of pure arbitrage.  

3. **Pre‑positioned cross‑exchange spot arbitrage**  
   - You pre‑split your capital: some USDT/USDC on Binance, some on Coinbase/Kraken, etc., and *don’t* move funds on‑chain per trade.
   - When spreads appear (e.g. BTC 60,000 on Binance, 60,200 on Kraken), you buy on one and sell on the other using existing balances.
   - Periodically rebalance transfers in bulk using the cheapest networks and only when the accumulated profit justifies a withdrawal fee.

These are the only families that consistently give small accounts a fighting chance.

***

## 3. Bot design rules for small capital

The core design principle: **model the full cost stack and reject 90%+ of naïve signals.**

### 3.1. Hard numeric filters

For each candidate trade, your bot should check:

- **All‑in fee estimate**:  
  - Spot/futures fee schedule (e.g. 0.1% per trade, 0.04% for some discounted tiers).
  - Expected slippage based on recent book depth (can approximate as 0.05–0.15% until you have your own stats).
- **Min spread requirement**:  
  - Same‑exchange triangular: spread > 3 × single‑trade fee, e.g. >0.3–0.4%.
  - Cross‑exchange spot with no transfer per cycle (pre‑positioned balances): spread > fees on both sides + slippage; in practice, usually >0.4–0.6% for small size.
- **Execution‑time cap**:  
  - If all legs can’t fill inside, say, 1–2 seconds, cancel and treat as failed opportunity.


## 4. Concrete strategies you can code

### 4.1. Single‑exchange triangular bot

On one liquid exchange (e.g. Binance or Kraken):

- Universe: 10–20 liquid coins + USDT/USDC.  
- For each triplet (A/B, B/C, A/C), compute implied vs actual cross rate; when deviation > threshold, trigger sequence.
- Fee‑aware formula from public examples: require theoretical vs market price to differ by at least 0.5% to cover three 0.1% trades + slippage.

Implementation hints (logic level, not code):

- Continuously stream orderbook best bids/asks for the triplets.  
- Simulate the three legs using *worst‑case* immediate‑or‑cancel prices for your size.  
- Only send real orders when simulated profit > minimum profit per trade (e.g. $0.50–$1 absolute plus percentage buffer).  

This strategy is inherently small‑capital friendly because there are no withdrawals, and the main constraint is speed and fee level.

### 4.2. Pre‑positioned cross‑exchange arb with bulk rebalancing

Given you already use BinanceUS, Kraken, and Coinbase:

- Decide a fixed base allocation (example: 40% of capital on Binance, 30% Kraken, 30% Coinbase).  
- Your bot:  
  - Continuously monitors spreads for a handful of pairs (BTC, ETH, maybe one or two high‑liquidity alts) across the three exchanges.
  - When spread > threshold (e.g. 0.6–0.8%), buy on low‑price venue, sell on high‑price venue using **existing** balances.  
  - Log total “virtual imbalance”: over time, one venue accumulates BTC, another accumulates USD.  
- When imbalance exceeds a limit and cumulative profit is comfortably above one bulk withdrawal fee, rebalance using the cheapest supported network (L2s, Solana, Tron etc.).

Public analyses highlight how newer L2s and cheap chains cut transfer time to minutes and cost to under 1 USD, reviving some inter‑exchange arb strategies that were killed by main‑chain gas.

***

## 5. How to validate your edge before risking real money

Given small capital, validation is critical:

- **Paper‑trade first**: Log every hypothetical trade with: timestamp, exchange(s), notional, all fees, and mark‑to‑market PnL. After a few thousand events, you will see if you actually beat 0.3–0.7% friction per cycle.
- **Build a realistic simulator**:  
  - Inject artificial latency (e.g. 200–500 ms), slip quotes a bit, and round your fills pessimistically.  
  - Use historical candles + synthetic spread models to stress‑test your thresholds.  
- **Track per‑strategy metrics**:  
  - Hit‑rate (% of opportunities that end profitable after costs).  
  - Average net edge per trade (in % and in USD).  
  - Worst slippage / failed trade loss.  
