# Triangular Arbitrage Path Logic Analysis

## Problem Found in Testing

Test detected 37,817% profit - **THIS IS WRONG**. Formula is correct but path interpretation is broken.

## Root Cause

The current logic treats paths as permutations WITHOUT understanding the actual currency flow.

### Example Path: `['ETH/USDT', 'ETH/BTC', 'BTC/USDT']`

Current logic:
- Leg 1: Buy at ETH/USDT ask (3150) → BUY ETH WITH USDT
- Leg 2: Buy at ETH/BTC ask (0.05) → BUY ETH WITH BTC (WRONG! We have ETH, not BTC)
- Leg 3: Sell at BTC/USDT bid (59900) → SELL BTC FOR USDT (WRONG! We have ETH, not BTC)

This creates a nonsensical flow that produces fake arbitrage.

## Correct Triangular Logic

For a valid triangular path with 3 pairs, we need to verify the **currency chain matches**.

### Valid Example: USDT → BTC → ETH → USDT

```
Pairs needed:
1. BTC/USDT (base=BTC, quote=USDT)
2. ETH/BTC  (base=ETH, quote=BTC)
3. ETH/USDT (base=ETH, quote=USDT)

Flow:
1. Start with USDT
2. Buy BTC with USDT (buy BTC/USDT at ask) → now have BTC
3. Buy ETH with BTC  (buy ETH/BTC at ask)  → now have ETH
4. Sell ETH for USDT (sell ETH/USDT at bid) → end with USDT

Profit = Final USDT - Starting USDT
```

## The Real Problem

**Permutations don't guarantee valid currency chains!**

`['ETH/USDT', 'ETH/BTC', 'BTC/USDT']` is a VALID permutation but an INVALID triangular because:
- ETH/USDT gives us ETH
- ETH/BTC wants us to have... ETH OR BTC (ambiguous!)
- BTC/USDT wants us to have BTC (but we might have ETH!)

## Solution

### Option 1: Validate Currency Chain
For each permutation, parse pairs and verify:
1. Leg 1 quote = starting currency
2. Leg 1 base = Leg 2 quote (or Leg 2 base if reversed)
3. Leg 2 base = Leg 3 base (or Leg 3 quote if reversed)
4. Leg 3 quote = starting currency

### Option 2: Build Paths Explicitly (BETTER)
Instead of permutations, construct valid paths:

```python
# For each starting currency (USDT, USD, USDC):
#   For each intermediate1 (BTC, ETH, SOL):
#     For each intermediate2 (BTC, ETH, SOL) where != intermediate1:
#       Check if path exists: start → int1 → int2 → start
```

This guarantees valid currency chains.

## Implementation Strategy

1. **Rewrite _generate_valid_triangular_paths()** instead of using permutations
2. For each path, explicitly define:
   - Which pair to use
   - Which side (buy/sell)
   - Which price (bid/ask)
3. Calculate profit with this explicit flow

## Estimated Fix Time

- 1 hour to rewrite path generation logic
- 30 min to update tests with correct expected profits
- 30 min to verify with real market data

**Status**: CRITICAL BUG - Must fix before deployment
