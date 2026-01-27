A well-built cryptocurrency trading bot follows a four-step cycle:

1. **Data Collection and Processing:**
- The bot continuosly monitors cryptocurrency markets in real-time.
- It retrieves the latest prices, order books, balances, and fees from exchanges.
- It uses live “WebSocket” connections for instantaneous updates.

2. **Calculations and Analysis:**
- Performs calculations privately within itself.
- The bot analyzes the data against strategy guidelines.

3. **Decision-Making:**
- Based on the analysis, the bot makes decisions.
-  Double-checks conditions before taking action.
- Ensures sufficient funds, safety, and adherence to rules.
- Analyzes external signals and internal health checks.
- Proceeds only if all conditions are met.
- This prevents 90% of losses.

4. **Trade Execution:**
- Places orders if conditions are met.
- Sends precise instructions to exchanges.
- Monitors orders, updates balances, and cleans up in case of timeouts, cancellations, or partial fills.
- Logs transactions and may rebalance wallets.
- Loops back to Step 1 for the next check.

This approach is crucial because execution directly interacts with real money, so simplicity, safety, and speed are essential. No sloppy code is used here or anywhere.

This modular and secure structure ensures reliable execution, mitigates common trading pitfalls, and facilitates adaptability to diverse strategies.

### The Overall Flow in One Sentence
The bot operates in a continuous loop: 

**Monitor markets → Calculate opportunities → Determine if execution is safe and profitable → Execute only if yes → Repeat.**

CURRENT STATUS: Currently 3 branches:
quant_bot clean: INCOMPLETE : components taken from quant_bot_2.1
quant_bot_final: a salvage attempt of quant_bot_clean
quant_bot_2.1: last known working version with LIVE real money executions.

qb_2.1 is monolithic and drains memory
qb_final is an impotent MVP prototype
qb_clean is what we want to work on!

The system operates in two primary modes based on a custom TradingView signal:

Macro Signal:
	* Fired (BUY BTC/SELL PAXG) on Nov 2023 = BTC Mode
	* Fired another signal on Nov 2025 (SELL BTC/BUY PAXG) = GOLD Mode.
Capital Allocation:
	* BTC Mode: 85% → [[Q-Bot]], 15% → [[A-Bot]], 0% → [[G-Bot]]
	* GOLD Mode: 15% → [[Q-Bot]], 0% → [[A-Bot]], 85% → [[G-Bot]]
System Components
1. [SIGNAL RECEIVER]
	* Always running in the background.
	* Listens for TradingView alerts (macro signal (mode flip) AND A-Bot (buy/sell) signals.
	* When something arrives, it immediately tells the Mode Manager or A-Bot when to buy/sell not what to do.
	* One job: Listens for TradingView alerts and passes them on. No polling, no timing.
2. [MODE MANAGER]
	* Holds the current state: BTC mode or GOLD mode.
	* Only changes when the [SIGNAL RECEIVER] tells it to (from Macro Signal).
	* Tells [MONEY MANAGER] which mode is active now.
	* Activates/deactivates bots DEPENDING on MODE
	* One job: remember the mode and announce/apply changes.
3. [[Q-Bot]]
	* SIMPLE Cross Exchange Arbitrage (80% of Qbot capital) (10s cycles)
	* TRIANGULAR Arbitrage (20% of Qbot Capital) (30s cycles)
	* BOTH:
	    * Run in tight continuous loop (every 10-30s, independent thread).
	    * Subscribes to fast WS data.
	    * Both take advantage of USDT and USDC prices
	    * Uses auction_context & order_executor logic
	    * Scans for arb opportunities (cross/triangular diffs).
	    * Calculates net profit (fees/slippage/transfers).
	    * Executes trades if profitable (limit/market mix, volume profiles, latency).
	    * Always active; uses its allocated capital share.
	    * One job: full arb cycle (scan + execute).
4. [MARKET SCANNER]
	* Compares price and order books to daily candle OHLC
	* Uses market_context logic (CVD, Wykoff, Wale Activity, VolProf)
	* Tells (Qbot when to be aggressive and when to be careful)
	* One job: watch for danger or opportunity in price swings.
5. [MONEY MANAGER]
	* Tracks every penny.
	* Divides the capital.
	* Checks account balances periodically (every few minutes).
	* If money is too uneven between exchanges (>15% drift), signals [TRANSFER MANAGER] AND [CONVERSION MANAGER] to move stablecoins to even it out (cheapest way).
	* Maintains a min dynamic BNB balance (logic already done).
	* Tells [TRANSFER MANAGER] AND [CONVERSION MANAGER] what it needs to maintain the ideal portfolio proportions across accounts for arbitrage, staking and gold sweeps!
	* One job: prevent capital from getting stuck in one account, divide and protect the shared fuel.
6. [CONVERSION MANAGER]
	* It is responsible for all conversions from one form of money to another outside triangular arbitrage.
	* It is basically an on demand triangular arbitrage machine with specified pairs and finds the cheapest AND fastest routes for the [MONEY MANAGER].
	* It tries to keep the drift across accounts below 15% by intra-exchange triangular conversions, so [[Q-bot]] runs smoothly.
	* Does not interrupt arbitrage system
	* One job: Reduces the amount needed to transfer by prioritizing triangular conversions (intra-exchange) over any cross-account transfers whenever possible to eliminate transfer fees entirely.
7. [TRANSFER MANAGER]
	* Transfers money across accounts after calculating the speed of transfer and transfer fees across accounts
	* Receives transfer route from [CONVERSION MANAGER].
	* Does not interrupt arbitrage system
	* Always queries real-time network fees & times, at execution (via exchange API (or ccxt)) and select the cheapest + fastest shared network between sender/receiver eg:
	* For Kraken → binanceus (USDT): Prefer Tron (TRC-20) or Solana → ~$0.50-1 fee, <5 min.
	* For binanceus → Coinbase (USDC): Prefer Solana, Polygon, or Base → <$0.10 fee, <5 min (Base often near-instant).
	* Adds safety check: Minimum transfer size $500+ (to avoid dust/minimums; simulate net cost (fee + slippage) before transferring).
	* One job: Keep average transfer cost per rebalance <$1 (achievable on above networks), ensuring operational costs stay <0.5% of capital annually.
8. [[A-Bot]]
	* Waits idle until [SIGNAL RECEIVER] gives a buy or sell signal.
	* On buy: uses its fuel share to buy the coin on the best exchange and stake it.
	* On sell: sells the coin on the best exchange.
	* If >3 slot is empty, automatically buy the highest-yield stakable coin, (seat warmer).
	* If <2 slot is empty automatically sell the “seat warmer” FIFO..
	* One job: handle the 6 long positions and staking when told.
9. [[G-Bot]]
	* Activates only in GOLD mode (told by Mode Manager).
	* Uses its fuel share to buy PAXG on the best exchange/pair.
	* IF {{MANUAL SWEEP}} is PRESSED during BTC MODE (max frequency, x1 a month), moves 15% of total profits to cold wallet in PAXG.
	* On mode flip to BTC, sells 85% of PAXG to free up fuel
	* keeps remaining 15% on a cold wallet
	* every cycle keeps 15%
	* One job: manage gold accumulation and sweeps.

Overall Strategy Notes (Cost-Reduction Emphasis, needs to be finalized)
* For the strategy to work in the real world we must emphasize intra-exchange triangular arbitrage (100% of Q-Bot cycles, ideally) to eliminate cross-account transfers during normal operations—zero transfer fees, full capital efficiency.
* Uses stablecoin pairs (USDT/USDC/USDG) on single exchanges to maximize 0.2-0.8% net edges without movement costs.
* Never use Ethereum (ERC-20) for transfers under $10k—fees often $0.87-5+ (volatile with congestion), times 5-15+ minutes. Avoid Avalanche unless specifically <$1 confirmed.
* Profitability Boost: By minimizing transfers via higher drift (8%) + low-fee networks, retain ~0.1-0.3% more per opportunity → potential 5-15% higher annual ROI on small capital vs. frequent/high-fee moves.

* For any required transfers, exclusively use the following & verify low-fee/fast stablecoin networks (USDT/USDC only; match sender/receiver support to prevent loss):
    * Tron (TRC-20 for USDT): Fees ~$0.50-1 (often under $1 for $1k equivalent); confirmation time <1-5 minutes. Widely supported on binanceus, Kraken, and many others—cheapest consistent option for USDT.
    * Solana: Fees <$0.01-0.10 (frequently near-zero); time <1-5 minutes (near-instant in low congestion). Excellent for both USDT and USDC; high adoption in 2026 for fast arb rebalancing.
    * Polygon (for USDC/USDT): Fees <$0.01-0.50; time <1-5 minutes. Strong for EVM-compatible exchanges; very low and predictable.
    * Base (Coinbase’s L2 for USDC): Fees ~$0.01-0.10; time ~1-2 seconds to near-instant. Ideal for Coinbase endpoints; reduces latency dramatically.
    * BNB Smart Chain (BEP-20 for USDT): Fees ~$0.01-1 (sometimes free on binanceus promotions); time <1-5 minutes. Zero or near-zero in many cases.
* Never use Ethereum (ERC-20) for transfers under $10k—fees often $0.87-5+ (volatile with congestion), times 5-15+ minutes. Avoid Avalanche unless specifically <$1 confirmed.
  
WHAT NEEDS TO BE DONE!!

We are reorganizing the code into a clean **hexagonal / ports & adapters** structure without changing the strategy, settings, or nomenclature.
- **adapters/**: Real implementations needed
- exchanges/: wrappers.py, binanceus.py (ccxt), kraken.py (krakenex), coinbaseadvanced.py (cbpro), and coinabse

- **core/**: Pure domain logic & calculations (no I/O, no external deps):
- profit.py (net/gross profit, slippage, fees, baseline 0.5%)
- risk.py (depth check, volatility slowdown) MERGED into health_monitor
- thresholds.py (dynamic 0.4–1% threshold)
- analysis.py (cvd, wykoff, volume profile, book analysis) MERGED into health_monitor!!

- auction.py (chase_limit, sizing, iceberg)

- order_executor.py (execution with risk checks)

- adapters/feed.py (WS data + short cache, WS-only)
- exchanges/wrappers.py (exchange REST/WS abstraction)

- **domain/**: Pure data types
- entities.py (Trade, Position, Signal, Mode)

- values.py (Price, Amount, Symbol, Network – all Decimal)
- aggregates.py (ArbOpportunity, Balance with drift)
- **manager/** (coordinators – short names): mode.py, money.py, conversion.py, transfer.py, scanner.py, ws.py, signals.py, fees.py, staking.py, health.py

- **ports/**: Interfaces
- inbound/: signal.py, command.py
- outbound/: prices.py, books.py, balances.py, execution.py, fees.py, ws.py

MISSING:  - persistence/: state.py, logs.py

-  **bots/**: Q.py, A.py, G.py (slim orchestration)

- **main.py** (merged main + system_orchestrator.py)

**Prioritized Tweaks** (must be integrated without changing strategy):
1. Baseline 0.5% net profit threshold How? -> Dynamic 0.4–1% threshold using auction/market signals
3. Depth check (top 5 volume > 2.5–5× trade size)
4. Volatility slowdown (double cycle time on high range)
5. We need live FRESH data : WebSocket-only for prices/books + short cache
6. Use official Coinbase & Kraken Python libraries

**Rules**:
- Never change the strategy, settings, or existing nomenclature.
- Use Decimal everywhere for money calculations.

Crypto Arbitrage Strategy: Exploiting Market Inefficiencies for Consistent Returns


├── main.py                       #work in progress!
    ├── system_orchestrator.py     	# copied and pasted into main.py and deleted
│
├── config/                    		
│   ├── coins.json
│   ├── settings.json             	
│   └── .env                   	 	# added  LATENCY_MODE='laptop'
│
│
├── adapters/
│   ├── data
│   │   ├── feed.py				
│   │   └── ws.py               
│   │
│   └─── persistance.         		# undone
│   │
│   └─── exchanges
│       ├── wrappers.py           
│       ├── binanceus.py          
│       ├── coinbase_advanced.py  
│       ├── coinbase.py           
│       └── kraken.py             
│
├── bot/
│   ├── Q.py						# arbitrage (cross + triangular)
│   ├── A.py				        # buy/sell + staking/unstaking
│   └── G.py                		# PAXG hedging & accumulation
│
├── core/
│   ├── auction.py              
│   ├── health_monitor.py       
│   ├── order_executor.py       
│   ├── profit.py               
│   └── thresholds.py		    
│
├── domain/                  
│   ├── aggregates.py			# *new
│   ├── entities.py			    # *new
│   └── values.py				# *new
│
├── logs/					
│   ├── errors/
│   ├── performance/
│   └── trades/
│
├── manager/
│   ├── fee.py	 		       # tracks all fees & "zero-fee" allowances per account
│   ├── mode.py         	   # state manager, broadcasts, de/activates bots
│   ├── money.py               # tracks and manages every cent
│   ├── converison.py          # Tries to keep drift below 15%
│   ├── transfer.py        	   # needs to fetch cheapest and fastest network 
│   ├── scanner.py      	   # notifies QBot of danger or opportunity in price.
│   ├── signals.py	 	        
│   └── staking.py              
│
│
├── dashboard.py             	# my visual window (keep this!)
├-- mini_dashboard.py	     	# a mini version of dashboard *(now = minidash.py needs integration into dashboard.py as a tab)
│
├── utils/
│   ├── helpers.py			    
│   ├── logger.py			    
│   └── utils.py                # refactored to here.
│
├── ports/						# new empty folder!!
│   ├── inbound/                # new empty folder!!
│   └──  outbound/              # new empty folder!!
│
├── services/                   # new empty folder!!
│
├── tests/                        #undone!
│   ├── component_testing/        #undone!
│   └── backtesting/              #undone!
│
└── state/                        #undone!

Summary: Prioritized Tweaks to Implement (Keep Strategy 100% Intact)
1. Set baseline threshold to 0.5% net (add to calculate_net_profit or config).
2. Make it dynamic (0.4–1% range) using auction/market context signals (highest ROI impact).
3. Add depth check (top 5 volume > 2.5–5× trade size) before execution.
4. Volatility slowdown (double cycle time on high range).
5. Reinforce WebSocket-only for prices/books + short cache
6. Coinbase & kraken have their own python libraries.
