# Conversion Manager Fix Strategy - FINAL PLAN

## Critical Discovery

**BOTH** `conversion.py` and `order_executor.py` have the same fundamental bug:
- They use arbitrary permutations
- They assume hardcoded buy/buy/sell sequence
- They don't validate currency chain compatibility

## The Right Approach (Per improvements.md)

For small accounts, triangular arbitrage should use **EXPLICIT, VALIDATED PATHS** only.

### Standard Triangular Patterns

#### Pattern 1: USDT → BTC → ETH → USDT
```
Leg 1: BUY  BTC/USDT at ask  (spend USDT, get BTC)
Leg 2: BUY  ETH/BTC  at ask  (spend BTC, get ETH)
Leg 3: SELL ETH/USDT at bid  (spend ETH, get USDT)
```

#### Pattern 2: USDT → ETH → BTC → USDT
```
Leg 1: BUY  ETH/USDT at ask  (spend USDT, get ETH)
Leg 2: SELL ETH/BTC  at bid  (spend ETH, get BTC)
Leg 3: SELL BTC/USDT at bid  (spend BTC, get USDT)
```

#### Pattern 3: USD → BTC → SOL → USD
```
Leg 1: BUY  BTC/USD at ask
Leg 2: BUY  SOL/BTC at ask
Leg 3: SELL SOL/USD at bid
```

### Key Insight

There are only **~10-15 valid triangular paths** worth checking for a small account!

Instead of checking 15! = 1,307,674,368,000 permutations (insane), we should:
1. Define the 10-15 profitable paths manually
2. Check only those paths
3. Use explicit buy/sell logic for each

## Recommended Implementation

### Step 1: Define Path Templates

```python
TRIANGULAR_PATHS = [
    # Format: (start_currency, path_pairs, actions)
    ('USDT', ['BTC/USDT', 'ETH/BTC', 'ETH/USDT'], ['buy', 'buy', 'sell']),
    ('USDT', ['ETH/USDT', 'ETH/BTC', 'BTC/USDT'], ['buy', 'sell', 'sell']),
    ('USDT', ['BTC/USDT', 'SOL/BTC', 'SOL/USDT'], ['buy', 'buy', 'sell']),
    ('USD', ['BTC/USD', 'ETH/BTC', 'ETH/USD'], ['buy', 'buy', 'sell']),
    # ... 10 more high-volume paths
]
```

### Step 2: Calculate Profit for Each Template

```python
def calculate_triangular_profit(books, path_def, fee_per_leg):
    start_currency, pairs, actions = path_def

    amount = Decimal('1')  # Start with 1 unit

    for pair, action in zip(pairs, actions):
        if action == 'buy':
            price = books[pair]['ask']  # Take from ask
            amount = (amount / price) * (Decimal('1') - fee_per_leg)
        else:  # sell
            price = books[pair]['bid']  # Hit the bid
            amount = (amount * price) * (Decimal('1') - fee_per_leg)

    profit_pct = (amount - Decimal('1')) * Decimal('100')
    return profit_pct
```

### Step 3: Execution Logic

```python
async def execute_triangular(exchange_id, path_def, trade_value_usd):
    start_currency, pairs, actions = path_def

    current_amount = trade_value_usd
    current_currency = start_currency

    for i, (pair, action) in enumerate(zip(pairs, actions)):
        if action == 'buy':
            # Calculate how much base currency we get
            price = get_ticker(pair)['ask']
            next_amount = current_amount / price
            execute_order(exchange_id, pair, 'buy', next_amount, price)
        else:  # sell
            price = get_ticker(pair)['bid']
            next_amount = current_amount * price
            execute_order(exchange_id, pair, 'sell', current_amount, price)

        current_amount = next_amount
        # Update current_currency by parsing pair

    return current_amount  # Final USDT received
```

## Decision: Simpler Fix or Full Rewrite?

### Option A: Quick Fix (2 hours)
1. Replace permutations with 10 hardcoded path templates
2. Update profit calculation to use explicit actions
3. Test with those 10 paths only
4. **Pros**: Works immediately, safe
5. **Cons**: Not generalized

### Option B: Full Rewrite (6 hours)
1. Build path validator that checks currency chains
2. Generate valid paths programmatically
3. Infer buy/sell actions from currency flow
4. **Pros**: Elegant, scales to any pairs
5. **Cons**: High complexity, more bugs

## Recommendation

**Option A** - Use hardcoded path templates.

### Reasoning (Per improvements.md):
- Small accounts should focus on **3-5 high-liquidity pairs** (BTC, ETH, SOL)
- This gives ~10-15 triangular paths maximum
- Checking 10 paths takes <5ms vs 1000ms for permutations
- **Selectivity > Generality** for small capital

## Implementation Checklist

- [ ] Define TRIANGULAR_PATH_TEMPLATES list (10-15 paths)
- [ ] Rewrite detect_triangle() to check only templates
- [ ] Add explicit action (buy/sell) to profit formula
- [ ] Update OrderExecutor.execute_triangular() to accept actions list
- [ ] Test with mock data
- [ ] Test with live Registry books in paper mode
- [ ] Commit with detailed explanation

## Time Estimate

- Define templates: 30 min
- Rewrite detect_triangle(): 1 hour
- Update execute_triangular(): 45 min
- Testing: 30 min
- **Total: 2.75 hours**

## Next Action

Create `conversion_v2.py` with template-based approach, test thoroughly, then replace original.
