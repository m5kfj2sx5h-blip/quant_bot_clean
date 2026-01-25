"""
Conversion Manager - Intra-Exchange Triangular Arbitrage

Responsible for all conversions from one form of money to another outside regular arbitrage.
An on-demand triangular arbitrage machine with specified pairs that finds the cheapest AND 
fastest routes for the Money Manager.

Tries to keep drift across accounts below 15% by intra-exchange triangular conversions,
so Q-Bot runs smoothly. Does not interrupt arbitrage system.

One job: Reduces the amount needed to transfer by prioritizing triangular conversions 
(intra-exchange) over any cross-account transfers whenever possible to eliminate transfer fees.
"""
import itertools
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Trading pairs for triangular routes
PAIRS = [
    'BTC-USD', 'ETH-USD', 'SOL-USD',
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT',
    'BTC-USDC', 'ETH-USDC', 'SOL-USDC',
    'ETH-BTC', 'SOL-BTC', 'SOL-ETH',
    'BTC-PAXG', 'PAXG-ETH', 'SOL-PAXG',
    'USD-USDT', 'USDT-USDC', 'USD-USDC'
]


class ConversionManager:
    """
    Manages intra-exchange triangular conversions to minimize transfer fees.
    Prioritizes triangular routes over cross-exchange transfers.
    """
    
    def __init__(self, config: Dict = None, exchanges: Dict = None):
        self.config = config or {}
        self.exchanges = exchanges or {}
        self.logger = logging.getLogger(__name__)
        self.capital_mode = "balanced"  # or "bottlenecked"
        
        # Drift threshold (15%)
        self.drift_threshold = Decimal('0.15')
        
        # Minimum profit for triangular route to be considered
        self.min_profit_pct = Decimal('0.08')
    
    def detect_triangle(self, books: Dict, specified_pairs: List = None, 
                        exchanges: List = None, min_prof: Decimal = None) -> List[Dict]:
        """
        Detect triangular arbitrage opportunities.
        
        Args:
            books: Order book data {'exchange': {'BTC-USD': {bids:[], asks:[]}, ...}}
            specified_pairs: Specific pairs to check (optional)
            exchanges: Specific exchanges to check (optional)
            min_prof: Minimum profit percentage (default 0.08%)
            
        Returns:
            List of opportunities sorted by profit (desc) then latency (asc)
        """
        min_prof = min_prof or self.min_profit_pct
        out = []
        
        pairs_to_check = specified_pairs or PAIRS
        exchanges_to_check = exchanges or list(books.keys())
        
        # Generate all 3-pair permutations
        paths = list(itertools.permutations(pairs_to_check, 3))
        
        for path in paths:
            for ex in exchanges_to_check:
                try:
                    # Parse the path to get base/quote for each leg
                    # Path example: ('BTC-USD', 'ETH-BTC', 'ETH-USD')
                    p0_base, p0_quote = path[0].split('-')
                    p1_base, p1_quote = path[1].split('-')
                    p2_base, p2_quote = path[2].split('-')
                    
                    # Get prices from order book
                    if path[0] not in books.get(ex, {}):
                        continue
                    if path[1] not in books.get(ex, {}):
                        continue
                    if path[2] not in books.get(ex, {}):
                        continue
                    
                    a = Decimal(str(books[ex][path[0]]['asks'][0][0]))
                    b = Decimal(str(books[ex][path[1]]['asks'][0][0]))
                    c = Decimal(str(books[ex][path[2]]['bids'][0][0]))
                    
                    # Calculate profit: start with 1 unit, go through triangle
                    prof = (Decimal('1') / a * Decimal('1') / b * c - Decimal('1')) * Decimal('100')
                    
                    if prof > min_prof:
                        out.append({
                            'exchange': ex,
                            'path': path,
                            'profit_pct': float(prof),
                            'prices': {'a': float(a), 'b': float(b), 'c': float(c)}
                        })
                        
                except (KeyError, IndexError, ZeroDivisionError):
                    continue
                except Exception as e:
                    self.logger.debug(f"Triangle detection error: {e}")
                    continue
        
        # Sort by profit descending
        return sorted(out, key=lambda x: -x['profit_pct'])
    
    def control_drift(self, drift_data: List[tuple], books: Dict = None) -> bool:
        """
        Control drift via intra-triangular conversions to eliminate transfer fees.
        
        Args:
            drift_data: List of (asset, deviation) tuples
            books: Current order books
            
        Returns:
            True if drift was controlled, False if manual transfer needed
        """
        if not drift_data:
            return True
        
        if not books:
            self.logger.warning("No order books available for drift control")
            return False
        
        for asset, deviation in drift_data:
            # Find triangular routes that can help rebalance this asset
            routes = self.detect_triangle(books)
            
            if routes:
                top = routes[0]
                self.logger.info(
                    f"Found triangular route for {asset} drift control: "
                    f"{top['path']} on {top['exchange']} ({top['profit_pct']:.2f}% profit)"
                )
                # Route found - can be executed by order executor
                return True
            else:
                self.logger.warning(
                    f"No triangular route for {asset} (deviation: {float(deviation)*100:.1f}%) - "
                    f"manual transfer may be needed"
                )
        
        return False
    
    def update_capital_mode(self, drift_data: List[tuple], total_stablecoins: Decimal):
        """
        Update capital mode based on drift and stablecoin levels.
        
        Args:
            drift_data: List of (asset, deviation) tuples
            total_stablecoins: Total stablecoin balance across exchanges
        """
        if not drift_data:
            max_deviation = Decimal('0')
        else:
            max_deviation = max((dev for _, dev in drift_data), default=Decimal('0'))
        
        # Bottleneck if drift > 15% OR stablecoins < $1500
        if max_deviation >= self.drift_threshold or total_stablecoins < Decimal('1500'):
            self.capital_mode = "bottlenecked"
        else:
            self.capital_mode = "balanced"
        
        self.logger.info(
            f"Capital mode: {self.capital_mode} "
            f"(max drift {float(max_deviation)*100:.1f}%, stables ${float(total_stablecoins):.0f})"
        )
    
    def get_best_conversion_route(self, from_asset: str, to_asset: str, 
                                   exchange: str, books: Dict) -> Optional[Dict]:
        """
        Find the best route to convert from one asset to another on a single exchange.
        
        Args:
            from_asset: Source asset (e.g., 'USDT')
            to_asset: Target asset (e.g., 'USDC')
            exchange: Exchange to use
            books: Order books
            
        Returns:
            Best route dict or None
        """
        # Direct route
        direct_pair = f"{from_asset}-{to_asset}"
        reverse_pair = f"{to_asset}-{from_asset}"
        
        if exchange in books:
            if direct_pair in books[exchange]:
                return {
                    'type': 'direct',
                    'pair': direct_pair,
                    'exchange': exchange,
                    'legs': 1
                }
            if reverse_pair in books[exchange]:
                return {
                    'type': 'direct_reverse',
                    'pair': reverse_pair,
                    'exchange': exchange,
                    'legs': 1
                }
        
        # Triangular route via BTC or ETH
        for intermediate in ['BTC', 'ETH', 'SOL']:
            if intermediate == from_asset or intermediate == to_asset:
                continue
            
            leg1 = f"{from_asset}-{intermediate}"
            leg2 = f"{intermediate}-{to_asset}"
            
            if exchange in books:
                if leg1 in books[exchange] and leg2 in books[exchange]:
                    return {
                        'type': 'triangular',
                        'path': [leg1, leg2],
                        'exchange': exchange,
                        'legs': 2
                    }
        
        return None
