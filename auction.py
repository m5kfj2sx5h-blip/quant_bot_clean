"""
Auction-Context Module – limit-chaser & auction-theory logic
"""
import logging
from typing import List, Tuple
from scanner import MarketContext, AuctionState
from decimal import Decimal

class AuctionContextModule:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_order_book(self, bids: List[Tuple[Decimal, Decimal]],
                           asks: List[Tuple[Decimal, Decimal]],
                           last_price: Decimal,
                           context: MarketContext) -> MarketContext:
        """Analyze order book to determine auction context"""
        try:
            if not bids or not asks:
                return context

            # Calculate top 5 levels imbalance
            bid_vol = sum(Decimal(str(qty)) for _, qty in bids[:5]) if len(bids[0]) > 1 else len(bids[:5])
            ask_vol = sum(Decimal(str(qty)) for _, qty in asks[:5]) if len(asks[0]) > 1 else len(asks[:5])

            if bid_vol + ask_vol > 0:
                context.auction_imbalance_score = (bid_vol - ask_vol) / (bid_vol + ask_vol)

            # Determines dynamic threshold based on approx Volume in USD
            # Small Account / Low Liq Tweak:
            # If volume is low (<$50k visible), a single whale order shouldn't trigger Panic Mode.
            # We relax the threshold from 0.3 to 0.6 for thin books.
            
            total_vol = bid_vol + ask_vol
            # Estimate Price from last_price or mid
            current_price = last_price if last_price > 0 else (Decimal(bids[0][0]) if bids else Decimal('1'))
            book_value_usd = total_vol * current_price
            
            # Dynamic Calibration for Small Account Bot
            base_threshold = Decimal('0.3')
            
            if book_value_usd < Decimal('10000'): # <$10k visible - Very Thin
                dynamic_threshold = Decimal('0.65') # Very loose
            elif book_value_usd < Decimal('50000'): # <$50k - Thin
                dynamic_threshold = Decimal('0.50') # Loose
            elif book_value_usd > Decimal('1000000'): # >$1M - Deep (BTC/ETH main)
                dynamic_threshold = Decimal('0.25') # Tight/Standard
            else:
                dynamic_threshold = base_threshold

            # Determine auction state using DYNAMIC threshold
            abs_score = abs(context.auction_imbalance_score)

            if abs_score < 0.1:
                context.auction_state = AuctionState.BALANCED
            elif context.auction_imbalance_score > dynamic_threshold:
                context.auction_state = AuctionState.IMBALANCED_BUYING
                context.crowd_behavior = "aggressive_buying"
            elif context.auction_imbalance_score < -dynamic_threshold:
                context.auction_state = AuctionState.IMBALANCED_SELLING
                context.crowd_behavior = "aggressive_selling"
            elif 0.1 <= abs_score <= dynamic_threshold:
                # Check price acceptance
                best_bid = Decimal(str(bids[0][0])) if bids[0] else 0
                best_ask = Decimal(str(asks[0][0])) if asks[0] else 0

                if best_bid and best_ask:
                    mid_price = (best_bid + best_ask) / Decimal('2')
                    
                    # Also relax acceptance criteria slightly for small accounts/noise
                    if abs(Decimal(str(last_price)) - mid_price) / mid_price < 0.002:
                        context.auction_state = AuctionState.ACCEPTING
                        context.crowd_behavior = "accepting_prices"
                    elif last_price > best_ask and context.auction_imbalance_score < 0:
                        context.auction_state = AuctionState.REJECTING
                        context.crowd_behavior = "rejecting_high_prices"
                    elif last_price < best_bid and context.auction_imbalance_score > 0:
                        context.auction_state = AuctionState.REJECTING
                        context.crowd_behavior = "rejecting_low_prices"
                    else:
                        context.auction_state = AuctionState.BALANCED
                        context.crowd_behavior = "balanced"

            # Set key levels if we have order book data
            if bids and asks:
                context.key_support = Decimal(str(bids[0][0])) * Decimal('0.995') if bids[0][0] else None
                context.key_resistance = Decimal(str(asks[0][0])) * Decimal('1.005') if asks[0][0] else None

            # Calculate volume strength (simplified)
            context.volume_strength = float(min(total_vol / Decimal('100.0'), Decimal('1.0')))  # Normalized

            self.logger.debug(f"Auction Analysis ({book_value_usd:,.0f}$): {context.auction_state.value} "
                              f"Score: {context.auction_imbalance_score:.3f} (Thresh: {dynamic_threshold:.2f})")

        except Exception as e:
            self.logger.error(f"❌ Auction analysis error: {e}")

        return context

    def limit_chase(book, side, size, max_slip=Decimal('0.02')):
        """Walk the book until size filled without exceeding max_slip.

        Returns dict {'price': float, 'qty': float, 'slip_pct': float} or None if cannot fill.
        """
        lvl = 0
        rem = size
        ttl_qty = 0
        wavg = 0

        # choose levels depending on side: if selling, we walk bids, else asks
        levels = book.get('bids') if side == 'sell' else book.get('asks')
        if not levels:
            return None

        try:
            ref = Decimal(str(levels[0][0]))
        except (IndexError, ValueError):
            return None

        while rem > 0 and lvl < len(levels):
            try:
                px = Decimal(str(levels[lvl][0]))
                avail = Decimal(str(levels[lvl][1]))
            except (IndexError, ValueError):
                break
            slip = abs(px - ref) / ref if ref else 0
            if slip > max_slip:
                break
            take = min(rem, avail)
            wavg += take * px
            ttl_qty += take
            rem -= take
            lvl += 1

        if ttl_qty == 0:
            return None

        avg_price = wavg / ttl_qty
        return {'price': avg_price, 'qty': ttl_qty, 'slip_pct': abs(avg_price - ref) / ref if ref else 0.0}

    def auction_micro_timing(book, side):
        """Return 0-1 score: 1 = perfect auction edge (thin book, wide spread)."""
        try:
            b = Decimal(str(book['bids'][0][0]))
            a = Decimal(str(book['asks'][0][0]))
        except (IndexError, ValueError):
            return 0.0
        spread = (a - b) / b if b else 0.0
        bid_depth = sum([Decimal(str(x[1])) for x in book.get('bids', [])[:5]])
        ask_depth = sum([Decimal(str(x[1])) for x in book.get('asks', [])[:5]])
        depth = min(bid_depth, ask_depth)
        return min(Decimal('1.0'), spread * Decimal('100') + Decimal('1.0') / (depth + Decimal('1.0')))

