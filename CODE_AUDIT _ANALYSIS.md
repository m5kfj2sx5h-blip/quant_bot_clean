🔍 COMPREHENSIVE CODE AUDIT & REMEDIATION PLAN
CONTEXT ANALYSIS
14+ hours work completed: Previous Gemini sessions identified major fixes (WebSocket string→list, database WAL mode, dashboard logic)
Current status: Bot functional but not actively trading (per verification_report.md)
Root cause: Conversion loop + threshold tuning needed
CRITICAL FINDINGS FROM DEEP-DIVE
✅ ALREADY FIXED (Confirmed in forensic_report.md)
WebSocket Initialization - String vs List bug fixed in feed.py:190-208
Database Concurrency - WAL mode enabled
Dashboard Logic - Case sensitivity fixed
Zero-Guessing Policy - Hardcoded fees removed per audit_report.md
🚨 CRITICAL ISSUES FOUND (New)
1. Coinbase Advanced SDK Misuse (adapters/exchanges/coinbase_adv.py)
Lines 43-70: Pagination logic has fallback risks
cursor check on line 85 may fail if API returns empty string
Risk: Infinite loop or missing balances
Line 31: Using get_transaction_summary() which may not exist in SDK
Should use get_transaction_summary_for_user() or equivalent
2. Kraken SDK Method Calls (adapters/exchanges/kraken.py)
Line 232: get_orders_info() expects specific format
May fail if res['result'][order_id] structure differs from expected
Line 226: Fallback to privatePostWithdraw is risky
Should use official SDK method only
3. BinanceUS Commission Calculation (adapters/exchanges/binanceus.py)
Lines 68-69: Treating commission as Decimal directly
makerCommission/takerCommission from Binance.US are integers (1-10000) representing basis points
BUG: Needs division by 10000
Current: 0.001 → Should be account['makerCommission'] / 10000
4. Order Executor Fill Verification (core/order_executor.py)
Lines 57-64: No wait for fill confirmation
Places order and immediately assumes success
Missing _wait_for_fill() implementation mentioned in audit_report.md
5. Decimal Precision Issues
Multiple files: Mixing float() and Decimal() conversions
bot/Q.py:128 uses float(amount) in place_order
Risk: Precision loss in financial calculations
6. WebSocket Data Callback (adapters/data/feed.py:101)
Line 101: Bare except catches callback errors silently
Should log which callback failed for debugging
⚠️ MEDIUM PRIORITY ISSUES
7. Conversion Manager (manager/conversion.py)
Not fully reviewed but referenced in verification_report as needing investigation
Likely missing profitable triangular detection logic
8. Transfer Manager Network Discovery (manager/transfer.py:126-128)
Line 128: Hardcoded network list fallback
Should rely on Registry exclusively or error gracefully
9. Q-Bot Profit Threshold (bot/Q.py:182-198)
Dynamic threshold logic solid but may be too conservative for small accounts
Consider: 0.4% min for BTC/ETH/SOL on high-liquidity pairs
📊 ARCHITECTURE COMPLIANCE
GOOD:
✅ Decimal usage for money (mostly correct)
✅ WebSocket implementation matches official docs
✅ 3-layer architecture preserved
✅ No CCXT usage (pure SDK calls)
NEEDS WORK:
⚠️ SDK method calls need validation against EXACT documentation
⚠️ Error handling too permissive (bare excepts)
⚠️ Missing fill verification loops
PROPOSED FIX SEQUENCE
PHASE 1: Critical SDK Fixes (Est: 30 min)
Fix Binance.US commission calculation (÷10000)
Fix Coinbase Advanced pagination cursor check
Add proper error handling to Kraken order fetching
Remove float() conversions in order placement
PHASE 2: Order Execution Safety (Est: 45 min)
Implement _wait_for_fill() in OrderExecutor
Add retry logic for partial fills
Add timeout protection (30s max wait)
PHASE 3: Conversion Loop Investigation (Est: 30 min)
Read manager/conversion.py fully
Add logging for triangular opportunity detection
Verify min_profit_pct threshold (should be 1.5% per README)
PHASE 4: Polish & Testing (Est: 45 min)
Replace bare except with specific exceptions
Add callback failure logging
Test with paper mode
Monitor one full cycle (10s + 30s)
PHASE 5: Documentation (Est: 30 min)
Update verification_report.md with fixes
Create FIXED_ISSUES.md summary
Git commit with detailed message
VERIFICATION CHECKLIST
All SDK calls match official docs exactly
No float() in money calculations
Fill verification implemented
Conversion loop logs opportunities
Bot completes one arb cycle without errors
Dashboard shows live data
ESTIMATED TOTAL TIME: 3 hours
Ready to proceed?