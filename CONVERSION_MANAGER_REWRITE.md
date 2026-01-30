# Conversion Manager Rewrite Plan

## Critical Issue Found
The `control_drift()` method I modified is still **detection-only** and doesn't execute trades. Per improvements.md, for small accounts (~$10k), same-exchange triangular arbitrage should be the PRIMARY strategy, not a fallback.

## Problems with Current Implementation

### 1. **Detection Without Execution**
- Lines 125-136: Logs opportunities but has TODO comment
- Returns True but no actual trade happens
- Bot thinks it handled drift but capital remains imbalanced

### 2. **Wrong Order Book Format**
- Line 54-56: Assumes `books[ex][pair]['asks'][0][0]` structure
- But our registry/data_feed uses different format
- Need to check actual book structure from Registry

### 3. **Incorrect Profit Calculation**
- Line 57: Formula `(1/a * 1/b * c - 1) * 100` is incomplete
- Missing fee deduction (3 legs × fee per leg)
- Per improvements.md: Must require profit > 3× single trade fee

### 4. **No Decimal Consistency**
- Line 54-56: Variables `a`, `b`, `c` are extracted as raw types
- Should be wrapped in Decimal() immediately
- Line 62: Converts to float() for storage (violates money calculation rule)

## Correct Implementation Per improvements.md

### Key Requirements:
1. **Min Spread**: > 0.3-0.4% for triangular (per improvements.md section 3.1)
2. **Fee Modeling**: Track all 3 legs, each ~0.1% (0.3% total minimum)
3. **Position Sizing**: ≤10% of equity per cycle
4. **Decimal for All Money**: Never use float in calculations

### Proper Triangular Formula:
```python
# Starting with 1 USDT
# Leg 1: Buy BTC with USDT at price_btc_usdt
btc_received = Decimal('1') / price_btc_usdt * (Decimal('1') - fee_leg1)

# Leg 2: Buy ETH with BTC at price_eth_btc
eth_received = btc_received / price_eth_btc * (Decimal('1') - fee_leg2)

# Leg 3: Sell ETH for USDT at price_eth_usdt
usdt_final = eth_received * price_eth_usdt * (Decimal('1') - fee_leg3)

# Net profit
profit_pct = (usdt_final - Decimal('1')) * Decimal('100')
```

## Action Plan

### Phase 1: Fix detect_triangle() [CRITICAL]
1. Verify actual book structure from Registry
2. Wrap all prices in Decimal()
3. Implement proper 3-leg fee-aware formula
4. Add position sizing check (max 10% TPV)
5. Test with mock data

### Phase 2: Implement execute_triangular() [CRITICAL]
1. Create new method that calls OrderExecutor
2. Pass detected opportunity to OrderExecutor.execute_triangular()
3. Calculate exact trade sizes based on book depth
4. Add slippage checks (per improvements.md: ~0.05-0.15%)
5. Return success/failure with actual PnL

### Phase 3: Integrate with control_drift() [CRITICAL]
1. Call execute_triangular() instead of just logging
2. Track execution results
3. Update drift state only if trade succeeds
4. Add cooldown to prevent spam (1 trade per asset per 30s?)

### Phase 4: Add Safety Checks [CRITICAL]
1. Verify sufficient balance for all 3 legs BEFORE starting
2. Add 1-2 second execution timeout (per improvements.md)
3. Emergency rollback if any leg fails
4. Persist trade records for analysis

## Test Strategy

### 1. Unit Tests (Mock Data)
- Test profit calculation with known prices
- Verify Decimal precision maintained
- Test edge cases (zero balance, missing pairs)

### 2. Integration Test (Paper Mode)
- Use live order books from Registry
- Simulate trades with OrderExecutor paper mode
- Verify no float() conversions in logs
- Confirm opportunities detected match manual calculation

### 3. Live Test (Small Size)
- Start with 1% of TPV max per trade
- Monitor first 10 executions closely
- Verify actual fills match expected
- Track cumulative fees vs profit

## Estimated Effort
- Phase 1: 1 hour (fix detection logic)
- Phase 2: 1.5 hours (implement execution)
- Phase 3: 30 minutes (integrate)
- Phase 4: 1 hour (safety + tests)

**Total: 4 hours**

## Next Steps
1. Read market_registry to verify book structure
2. Read order_executor.execute_triangular() to understand integration points
3. Write corrected detect_triangle() with Decimal everywhere
4. Test with mock books before touching real code
