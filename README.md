## Agent Instructions
Review official docs:  
- https://github.com/coinbase/coinbase-advanced-py/  
- https://docs.kraken.com/api/docs/guides/global-intro  
- https://docs.binance.us/#introduction  

***this file is not working properly, it is not connected together properly***
This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

### The 3-Layer Architecture

**Layer 1: Directive (What to do)**  
- Markdown SOPs in `directives/` (or embedded here).  
- Define goals, inputs, tools/scripts to use, outputs, edge cases.  
- Natural language instructions, like you'd give a mid-level employee.

**Layer 2: Orchestration (Decision making)**  
- This is you (the AI). Your job: intelligent routing.  
- Read directives, call execution tools/scripts in the right order, handle errors, ask for clarification, update directives with learnings.  
- You're the glue between intent and execution. E.g., don't try scraping websites yourself—read `directives/scrape_website.md` and run `execution/scrape_single_site.py`.  
- Focus on decision-making; push complexity to deterministic code.

“Before writing any code, scan and quote the exact balance-fetching examples from the linked official docs—Binance, Kraken, Coinbase—treat them as gospel, no shortcuts, no CCXT, just pure SDK calls.this is MUST just as using Decimal is MUSt with money”

**Layer 3: Execution (Doing the work)**  
- Deterministic Python scripts in `execution/` (or equivalent).  
- Environment variables, API tokens, etc. stored in `.env`.  
- Handle API calls, data processing, file operations, database interactions.  
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** If you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

### Operating Principles

1. **Check for tools first**  
   Before writing a script, check existing ones in `execution/` per your directive. Only create new scripts if none exist.

2. **Self-anneal when things break**  
   - Read error message and stack trace.  
   - Fix the script and test it again (unless it uses paid tokens/credits/etc.—in which case check with user first).

Now apply this architecture to the project below.

## Project Goal & Hexagonal Refactor Instructions

This is a cryptocurrency arbitrage and hedging bot designed for a ~$10,000 budget in January 2026.

### Core Strategy (100% to be preserved)
# System Visual Architecture
### Core Strategy (100% to be preserved)

The system operates in two primary modes based on a custom TradingView signal:

Macro Signal:
    * Fired (BUY BTC/SELL PAXG) on Nov 2023 = BTC Mode
    * Fired another signal on Nov 2025 (SELL BTC/BUY PAXG) = GOLD Mode.
Capital Allocation:
    * BTC Mode: 85% → [Q-Bot], 15% → [A-Bot], 0% → [G-Bot]
    * GOLD Mode: 15% → [Q-Bot], 0% → [A-Bot], 85% → [G-Bot]
System Components
1. [SIGNAL RECEIVER]
    * Listens for TradingView alerts (Macro Signal (mode flip) AND [A-Bot] (buy/sell) signals.
    * When something arrives, it immediately tells the Mode Manager or [A-Bot] when to buy/sell not what to do.
    * One job: Listens for TradingView alerts and passes them on. No polling, no timing.
2. [MODE MANAGER]
    * Holds the current state: BTC mode or GOLD mode.
    * Only changes when the [SIGNAL RECEIVER] tells it to (from Macro Signal).
    * Tells [MONEY MANAGER] which mode is active now.
    * Activates/deactivates bots according to BTC Mode or GOLD Mode
    * One job: remember the mode and announce/apply changes.
5. [MONEY MANAGER]
    * Tracks every penny.
    * Divides the capital for ALL.
    * Checks account balances periodically.
    * If [Q-Bot] arbitrage money becomes too uneven between accounts (>35% drift), signals [TRANSFER MANAGER] AND [CONVERSION MANAGER] to move USDT/USDC across accounts to even it out THE cheapest way.
    * Does not interrupt [Q-Bot]
    * Tells [TRANSFER MANAGER] AND [CONVERSION MANAGER] what it needs to maintain the ideal portfolio proportions across accounts for arbitrage.
    * MULTIPLE JOBS: Divide and allocate capital. Prevent capital from accumulating in one account. 
6. [CONVERSION MANAGER]
    * It tries to keep drift <15% across exchanges by PROFITABLE INTRA-EXCHANGE triangular conversions (min profit >=1.5%).
    * Does not interrupt [Q-Bot]
    * One job: Reduces the amount needed to transfer by prioritizing internal triangular conversions (intra-exchange) over any cross-account transfers whenever possible to eliminate transfer fees entirely.
7. [TRANSFER MANAGER] 
    * Transfers USDT OR USDC across accounts after calculating the speed of transfer and transfer fees across accounts
    * Receives transfer route from [CONVERSION MANAGER].
    * Does not interrupt [Q-Bot]
    * Always queries real-time network fees & times, at execution time and select the cheapest + fastest shared network between sender/receiver
    * Kraken <-> Binance.US can use USDT/USDC
    * Coinbase <-> Binance.US/KRAKEN use USDC ONLY!
    * ADDRESSES & networks:
      ##### BINANCE.US Wallets:
        - Network_SOL: 6nVkZ9DhUGpCSikwmwykjZkPCJkQEASVKKnrEScj3Ya8
          - deposit: USDT, USDC, SOL
        - Network_AVAX C-Chain: 0x9433ef65333256178a317bdefb8c18ad49b22350
          - deposit: USDT, USDC
        - Network_TRON (TRC20): THiAU5ReTWR9TBWVTv1WRKBY7j9qeZXFkw
          - deposit: USDT
      ##### KRAKEN Wallets: 
        - Network_SOL: FnFSRzQDSa1kfFKABS6onFid1yncwYC6TqKcCXe2bcQa
          - deposit : USDC, USDT, SOL
        - Network_AVAX C-Chain: 0x18791c1Ec171169B4E599A01D280a325500f1BB5
          - deposit: USDC, USDT
        - Network_Sui: 0x29d57083b1b274d6e78155c147f87a9964b8a9e0e28b890ec10a984447e35eab
          - deposit: USDC, SUI
        - Network_Algo: SMN5HNKR45Z6GB546A5KRI2AGODAYKSPMXLGL5PB5SFY6URD4MANLLAPKI
          - deposit: USDC
        - Network_TRON (TRC20): TLEvYy9aYUztMYqxvXcLshEdvqWwNFysMK
          - deposit: USDT
      ##### Coinbase USDC ONLY Wallets:
        - Network_SOL: rfXgbu6jQVgEThszwPBvCgHPq2LX59m4qZSLbneqczw
        - Network_AVAX C-Chain: 0x27FA5C63e7f7c2D07b349A8F44cc29870A32f8C6
        - Network_Sui: 0xc8cb27799a08da6f64e77f1267d3330fb5e01b13d6cbad1914e81ce069dc4ed6
        - Network_Algo: XFDI7INMVW32QUKO4QRBHNOIGSNA5AOX2MVWP5DHH3PUXX4JOCPWBF46AU
      ##### Coinbase Alt Wallets:
        - Network_SOL_2: Ch2d4gvee8jnJ384xacj4bsp3YWKAG9yMDS2u2MeWmcw
          - deposit: SOL 
        - Network_Sui_2: 0xf36f79b4353442fe95b5ddeaa2dafeada617d67b598ea1cf0d3d41a3153e5e61
          - deposit: SUI
    * Adds safety check: Minimum transfer size $500+ (to avoid dust/minimums; simulate net cost (fee + slippage) before transferring).
    * One job: Keep average transfer cost per rebalance <$1 (achievable on above networks), ensuring operational costs stay <0.5% of capital annually.
8. [Q-Bot]
    * SIMPLE Cross Exchange Arbitrage (80% of [Q-Bot] capital) (10s cycles)
      * [BTC/USD/USDT/USDC]
      * [ETH/USD/USDT/USDC]
      * [SOL/USD/USDT/USDC]
    * TRIANGULAR Cross Exchange Arbitrage (20% of [Q-Bot] Capital) (30s cycles)
      * [X <-> Y <-> USD/USDT/USDC] 
      * [X <-> USD/USDT/USDC <-> Y]
      * [USD/USDT/USDC <-> X <-> Y]
      *  X or Y = BTC/ETH/SOL
    * BOTH:
        * Run in tight continuous loops (independent parallel threads).
        * Subscribes to fast WS data.
        * Both take advantage of USDT and USDC prices
        * Uses auction_context & order_executor logic
        * Scans for arb opportunities (cross/triangular diffs).
        * Calculates net profit (fees/slippage/transfers).
        * Executes trades if profitable (limit/market mix, volume profiles, latency).
        * Always active; uses its allocated capital share.
        * One job: full arb cycle = x3(simple) + x1(triangular).
10. [A-Bot]
    * Waits idle until [SIGNAL RECEIVER] gives a buy or sell signal.
    * On buy: uses its allocated share to buy the coin on the best exchange and stake it.
    * On sell: sells the coin on the best exchange.
    * If >3 slot is empty, automatically buy the highest-yield stakable coin, (seat warmer).
    * If <2 slot is empty automatically sell the “seat warmer” FIFO..
    * One job: handle the 6 long positions and staking when told.
11. [G-Bot]
    * Activates only in GOLD mode.
    * Uses its allocated share to buy PAXG on the best exchange/pair.
    * IF [MANUAL SWEEP] is PRESSED during BTC MODE (max frequency, x1 a month), moves 15% of total profits to BASE wallet in PAXG.
    * On mode flip to BTC, sells 85% of PAXG to free up fuel
    * Keeps remaining 15% on BASE wallet
    * Every cycle keeps 15%
    * One job: manage gold accumulation and sweeps.
9. [MARKET SCANNER]
    * Compares price and order books to daily candle OHLC
    * Uses market_context logic (CVD, Wykoff, Wale Activity, VolProf)
    * Tells [Q-Bot] when to be aggressive and when to be careful
    * One job: watch for danger or opportunity in price swings.
12. [FEE MANAGER]
     * Fetches lowest combined buy/sell fees
     * Maintains a min dynamic BNB balance.
     * Tracks 'zero fee' allowances per month for each account
     * One job: monitor and manage fees
**Rules**:
- Never change the strategy, settings, or existing nomenclature without approval and confirmation.
- Use Decimal everywhere for money calculations.

