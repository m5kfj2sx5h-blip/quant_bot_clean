from utils.utils import log
from decimal import Decimal
import os
from core.health_monitor import HealthMonitor  # For dynamic speeds if latency metrics

class TransferManager:
    def __init__(self, exchanges, stable, auto):
        self.exchanges = exchanges
        self.stable = stable
        self.auto = auto
        self.latency_mode = os.getenv('LATENCY_MODE', 'laptop').lower()
        self.health = HealthMonitor()  # For dynamic speeds
        self.supported_nets = ['TRC20', 'ERC20', 'SOL', 'BASE', 'MATIC', 'AVAX', 'ARB', 'OP']  # From research
        logger.info(f" ✅ Supported nets: {self.supported_nets}")

    def balance_accounts(self):
        balances = {name: Decimal(str(ex.fetch_balance().get('total', {}).get(self.stable, 0))) for name, ex in
                    self.exchanges.items()}
        avg = sum(balances.values()) / Decimal(len(balances))

        def balance_accounts(self):
            balances = {name: Decimal(str(ex.fetch_balance().get('total', {}).get(self.stable, 0))) for name, ex in
                        self.exchanges.items()}
            avg = sum(balances.values()) / Decimal(len(balances))

            for name, bal in balances.items():
                if bal < avg * Decimal('0.9'):
                    from_name = max(balances, key=balances.get)
                    amount = (avg - bal) / Decimal('2')
                    # Pre-calc best net/fee/speed
                    best_fee, best_net, best_speed = self.get_best_net(from_name, name, amount)
                    if best_fee is None:
                        log(f"No suitable net for transfer {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name}")
                        continue
                    log(f"Best net: {best_net} (fee {best_fee.quantize(Decimal('0.00'))}, speed {best_speed}s)")
                    if self.auto:
                        self.exchanges[from_name].withdraw(self.stable, str(amount),
                                                           self.exchanges[name].fetch_deposit_address(self.stable)[
                                                               'address'], {'network': best_net})
                        log(f"✅ AUTO X TRANSFER {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name} via {best_net}")
                    else:
                        log(f"⚠️ MANUAL X TRANSFER NEEDED!! ⚠️: {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name} via {best_net}, fee {best_fee.quantize(Decimal('0.00'))}")

    def get_best_net(self, from_name, to_name, amount: Decimal):
        """Calc fees/speeds before transfer, choose best (cheapest + fastest), avoid ERC20 < $10k."""
        fees = self.exchanges[from_name].fetch_deposit_withdraw_fees([self.stable])
        nets = fees[self.stable]['networks']
        candidates = []
        for net in self.supported_nets:
            if net in nets:
                fee = Decimal(str(nets[net]['withdraw']['fee']))
                speed = self.health.latency_metrics[from_name][-1] if self.health.latency_metrics[
                    from_name] else Decimal('10')  # Dynamic from health, default 10s
                if net == 'ERC20' and amount < Decimal('10000'):
                    continue  # Avoid ERC20 < $10k
                score = fee + (speed * Decimal('0.1'))  # Weight fee more, adjust as needed
                candidates.append((fee, net, speed, score))
        if not candidates:
            return None, None, None
        best = min(candidates, key=lambda x: x[3])  # Min score
        return best[0], best[1], best[2]

    def get_transfer_fee(self, from_name, to_name):
        fees = self.exchanges[from_name].fetch_deposit_withdraw_fees([self.stable])
        nets = fees[self.stable]['networks']
        best_net = min(nets, key=lambda n: nets[n]['withdraw']['fee'])
        return Decimal(str(nets[best_net]['withdraw']['fee'])), best_net

    def transfer(self, asset, from_name, to_name, amount: Decimal):
        if self.auto:
            net = 'TRC20' if 'TRC20' in self.exchanges[from_name].currencies[asset]['networks'] else 'ERC20'
            address = self.exchanges[to_name].fetch_deposit_address(asset)['address']
            self.exchanges[from_name].withdraw(asset, amount, address, {'network': net})