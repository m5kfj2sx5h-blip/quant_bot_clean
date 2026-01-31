# quant_bot_clean - _FIXED Branch is the only branch to focus on!

_FIXED is still not working properly, it is not connected together properly. 

## Agent Instructions

Review official docs:

This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. 
LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. 
This "3 layer Development Method" fixes that mismatch.

### The 3-Layer Development Method

Layer 1: Directive (What to do)

- Markdown SOPs in `directives/`(create a new folder in current project root folder).
- Define goals, inputs, tools/scripts to use, outputs, edge cases.
- Natural language instructions, like you'd give a mid-level employee.

Layer 2: Orchestration (Decision making)

- This is you (the AI). Your job: intelligent routing.
- Read directives, call execution tools/scripts in the right order, handle errors, ask for clarification, update directives with learnings.
- You're the glue between intent and execution.
- Focus on decision-making; push complexity to deterministic code.

“Before writing any code, check the following links, and verify the exact balance-fetching methods, execution methods and every other method we need from each exchange or account for BinanceUS, Kraken, Coinbase advanced, Coinbase (regular)  this is a MUST just as using Decimal is MUST with money” 
treat these links as gospel, no shortcuts, no CCXT, use the official software development kits (SDK) provided by each account BinanceUS, Kraken+, Coinbase One (they define the methods we need to do what i want to build). - https://github.com/coinbase/coinbase-advanced-py/
- https://docs.kraken.com/api/docs/guides/global-intro  
- https://docs.binance.us/#introduction  

Layer 3: Execution (Doing the work)

* Deterministic Python scripts in root folder.
* Environment variables, API tokens, etc. stored in `.env`.
* Handle API calls, data processing, file operations, database interactions.
* Reliable, testable, fast. Use scripts instead of manual work. Commented well.

***ALWAYS PAY ATTENTION TO THE GREYED OUT #COMMENTS IN-CODE, and place any undone tasks from these in-code comments in the Markdowns you create in '/directives'***

Why this works: If you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

### Operating Principles
0. Check links, tools/scripts first
  Before writing a script, check existing ones in 'directives/` per your directive. Only create new scripts if none exist.
1. Self-anneal when things break
  - Read error message and stack trace.
  - use chain of thought to find the root cause of errors
  - LOOK for any similar errors or traces elsewhere
  - group similar or related errors together
  - plan a solution and update directives
  - Fix the script and test it again 

Now apply this '3-Layer Development Method' to the project below.
## Project Goal & Instructions
This is a small account cryptocurrency arbitrage and gold accumulation bot, designed for a ~$10,000 budget in January 2026.

##### Refactor to HEXAGONAL Architecture 
all files are currently in root folder, so everything stays visible for now, once project is 99% complete, I can easily put the .py files back in their respective folders

##### Arbitrage Capital & Risk Management Rules
This system exists to maximize arbitrage profitability while preserving capital.
It is not a balance equalization tool, and it must never behave like one.
All capital movement, conversion, and liquidation decisions must be justified by profitability or risk reduction, not by fixed balance targets.

##### Transfer Policy
Transfers are a last-resort tool, not a default mechanism.
	•	Transfers are allowed only when internal conversion is no longer profitable, or when transferring is cheaper and faster for capturing a profitable arbitrage opportunity.
	•	Transfers must never be executed solely to rebalance accounts to predetermined levels.
	•	Fixed balance targets are explicitly disallowed, as they force buying during market drawdowns and introduce unnecessary risk.

##### Internal Conversion Policy
When transfers are disabled — or when internal conversion is cheaper and faster — the system must:
	•	Prefer intra-exchange conversions to reduce asset drift.
	•	Execute conversions only if they improve expected arbitrage profitability or future execution capacity.
	•	Avoid conversions that exist purely to normalize balances.

-> Internal conversion serves arbitrage execution, not accounting symmetry.

##### Global Money Management
The Money Manager operates on the entire portfolio, not just individual accounts.
It must:
	•	Monitor all open positions and balances across every exchange as a unified exposure.
	•	Use VWAP and liquidity data already collected in liquidity.py to evaluate true P&L and drawdown risk.
	•	Identify volatility conditions where arbitrage efficiency degrades and execution risk rises.
	•	Actively reduce or liquidate positions to preserve accumulated profit when risk exceeds expected return.

-> In volatile markets, arbitrage naturally slows while risk increases.
Capital preservation takes priority over continued execution.

##### Data Usage Requirement
The system aggregates extensive market and liquidity data. This data must be used to:
	•	Evaluate conversion and transfer profitability
	•	Measure real exposure and loss, not nominal balances
	•	Inform liquidation and risk-off decisions

-> Unused data represents a failure in system design, not an implementation detail.

### Design Constraint
Any action that does not:
	•	Increase arbitrage profitability, or
	•	Reduce portfolio-level risk
must be considered invalid behavior.

### Core Strategy (100% to be preserved)
The system operates in two primary modes (RISK ON / RISK OFF) based on a custom TradingView signal:

#### Macro Signal: 
    
   * Fired (buy BTC/ sell PAXG) on Nov 2023 = BTC Mode (RISK ON)
   * Fired another signal on Nov 2025 (sell BTC/ buy PAXG) = GOLD Mode. (RISK OFF) 
    
#### Capital Allocation: 
 
   * BTC Mode: 85% → [Q-Bot], 15% → [A-Bot], 0% → [G-Bot] 
   * GOLD Mode: 15% → [Q-Bot], 0% → [A-Bot], 85% → [G-Bot] 

### System Components

1. [SIGNAL RECEIVER]
  * Listens for TradingView alerts 1. Macro Signal (mode flip) 2. [A-Bot] (buy/sell) signals.
  * When something arrives, it immediately tells the Mode Manager or [A-Bot] when to buy/sell not what to do.

2. [MODE MANAGER]
  + Holds the current state: BTC mode or GOLD mode.
  + Only changes when the [SIGNAL RECEIVER] tells it to (from Macro Signal).
  + Tells [MONEY MANAGER] which mode is active now.
  + Activates/deactivates bots according to BTC Mode or GOLD Mode

3. [MONEY MANAGER] 
  * Tracks every penny.
  * Divides the capital for ALL.
  * Checks account balances periodically.
  * Tracks value of every account and liquidates positions if necessary, look at 'Global Money Management' above.
  * If [Q-Bot] arbitrage money becomes too uneven between accounts (>50% drift), signals [TRANSFER MANAGER] OR [CONVERSION MANAGER] OR BOTH.
  * Does not interrupt [Q-Bot].
  * uses [TRANSFER MANAGER] AND [CONVERSION MANAGER] to achieve its goal.

4. [CONVERSION MANAGER]
  * It tries to keep drift <35% across exchanges by PROFITABLE INTRA-EXCHANGE triangular conversions (min profit 0.8-1.5% depending on drift severity).
  * Does not interrupt [Q-Bot].

5. [TRANSFER MANAGER]
  * Transfers USDT, USDC, or SOL across accounts after fetching transfer speed and transfer fees
  * Receives the desired transfer route from [MONEY MANAGER].
  * Does not interrupt [Q-Bot]
  * Always queries real-time network fees & times, at execution and selects the cheapest + fastest shared network between sender/receiver
  * Kraken <-> Binance.US can use USDT/USDC/SOL
  * Coinbase <-> Binance.US/KRAKEN use USDC/SOL
  * Adds safety check: Minimum transfer size $500+ (to avoid dust/minimums; simulate net cost (fee + slippage) before transferring).
  * ADDRESSES & networks: [listed wallets and networks in config/Transfer_Wallets.md]

6. [Q-Bot]
  * SIMPLE Cross Exchange Arbitrage (80% of [Q-Bot] capital) (RUNS as fast as possible)
  * Buys crypto at 'cheap exchange' AND sell same crypto at 'expensive exchange'
  * UTILIZES any currency available AND CONVERTS IT TO THE TYPE IT NEEDS FOR THE MOST PROFITABLE PATH! 
  * Monitors prices differences for BTC ,ETH and SOL across the three exchanges in USD, USDT and USDC
  * That is a total of 9 pairs across 3 accounts!

     Kraken          BinanceUS            Coinbase
   1. BTC/USD         BTC/USD              BTC/USD
   2. BTC/USDT        BTC/USDT             BTC/USDT
   3. BTC/USDC        BTC/USDC             BTC/USDC

   4. ETH/USD         ETH/USD              ETH/USD
   5. ETH/USDT        ETH/USDT             ETH/USDT
   6. ETH/USDC        ETH/USDC             ETH/USDC

   7. SOL/USD         SOL/USD              SOL/USD
   8. SOL/USDT        SOL/USDT             SOL/USDT
   9. SOL/USDC        SOL/USDC             SOL/USDC


  * TRIANGULAR (INTRA) Exchange Arbitrage (20% of [Q-Bot] (RUNS as fast as possible)
    1. BTC -> SOL -> ETH -> BTC
    2. BTC -> ETH -> SOL -> BTC
    2. ETH -> SOL -> BTC -> ETH
    3. ETH -> BTC -> SOL -> ETH
    4. SOL -> ETH -> BTC -> SOL
    3. SOL -> BTC -> ETH -> SOL 
    4. BTC -> SOL -> BTC
    5. BTC -> ETH -> BTC
    5. ETH -> BTC -> ETH
    6. ETH -> SOL -> ETH
    6. SOL -> BTC -> SOL
    7. SOL -> ETH -> SOL

  * Run in tight continuous loops (independent parallel threads).
  * Subscribes to fast WS data.
  * Uses auction_context & order_executor logic
  * Scans for arb opportunities (cross/triangular diffs).
  * Calculates net profit (fees/slippage/transfers).
  * Executes trades if profitable (limit/market mix, volume profiles, latency).
  * Always active; uses its allocated capital share.

# Rules:
* Never change the strategy, settings, or existing nomenclature without approval and confirmation.
* Use Decimal everywhere for money calculations.

## Critical Implementation Gaps & Required Fixes (from diagnostics)

Cross-exchange scanning partially works. But core blockers prevent reliable execution.


**Critical flaws to fix (priority order):**

1. **Conversion Manager**: Broken—generates random/invalid triangular paths, hardcoded buy/buy/sell sequences, nonsensical profits (e.g., 37k%), no execution flow. Blocks 20% of Q-Bot capital (intra-exchange triangular). Must rewrite to use fixed path templates, explicit buy/sell legs, full Decimal cost stack (fees + slippage), min net profit 0.4%, safety checks (balance pre-check, cooldowns, rollback on partial fill).

2. **Order fills & execution**: Polling in _wait_for_fill() (REST status loops, 5s timeout). Switch to websocket callbacks for trade/order updates—Kraken, Binance.US, Coinbase all support WS fill events. No polling in hot paths.

3. **Data feeds**: Mix of REST in scanners/conversion—kills rate limits and adds 100-500ms latency. Force all price/order-book data through websockets only (subscribe once, event-driven on tick). No polling loops anywhere.

4. **Cycle timing**: 10s cross / 30s triangular batches—too slow for real arb (edges vanish <2s). Make fully event-driven: trigger triangular/cross scan on every WS tick delta. Full cycle (tick → compute → orders → fills) must be <2-3s end-to-end, ideally <1s for triangular.

5. **Async & blocking**: No explicit async/await in order_executor or hot loops—synchronous placement blocks threads. Use asyncio everywhere for parallel orders, WS handling, reconnections with exponential backoff.

6. **Safety & validation**: No pessimistic cost simulation, no hit-rate logging, no paper-trade mode with latency/slippage injection. Add pre-trade balance checks, reject if net < threshold, log all attempts.

**Fix plan:**
- one file per exchange → subscribe_ws_prices() (stream BTC/USD/USDT/USDC, ETH/USD/T/C, SOL/USD/T/C), place_order_async(), get_balance_decimal().

~~- Q-Bot: on_ws_tick() → first run intra-exchange triangular (fixed templates, Decimal math), if no edge → cross only if pre-split balances sufficient.~~
- Conversion Manager rewrite: template-based paths, async 3-leg execution, WS fill confirm.
- Test: paper mode first (simulate WS feeds), log latency per cycle, net edge after fees/slippage.

- No new endpoints. No CCXT. No floats. No polling.

Read /directives and this README fully before coding. Use official docs verbatim for WS/REST endpoints. 
Wire fast, event-driven, Decimal-safe. 
Fix these gaps and the bot will run the strategy as designed.

**Fix plan (continued):**
- Implement Decimal-based balance checks and order placement.
- Refactor Q-Bot to handle intra-exchange triangular trades and cross trades based on pre-split balance checks.
- Rewrite Conversion Manager to use template-based paths and asynchronous 3-leg executions, leveraging WebSocket fill confirmation.
- Conduct thorough testing in paper mode, simulating WebSocket feeds, and logging latency and net edges after fees and slippage.
- Ensure all critical operations are asynchronous and event-driven to maintain responsiveness and prevent blocking.
- Validate all operations using Decimal arithmetic to prevent floating-point precision issues.
