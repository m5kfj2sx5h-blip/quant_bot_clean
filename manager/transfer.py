from utils.utils import log
from decimal import Decimal
import os
from core.health_monitor import HealthMonitor
from dotenv import load_dotenv

load_dotenv()

class TransferManager:
    def __init__(self, exchanges, stable, auto):
        self.exchanges = exchanges
        self.stable = stable
        self.auto = auto
        self.latency_mode = os.getenv('LATENCY_MODE', 'laptop').lower()
        self.health = HealthMonitor()
        self.supported_nets = []  # Dynamic
        self._fetch_supported_nets()

    def _fetch_supported_nets(self):
        self.supported_nets = []
        for exchange in self.exchanges.values():
            fees = exchange.fetch_deposit_withdraw_fees(['USDT'])
            nets = list(fees['USDT']['networks'].keys())
            for net in nets:
                if net not in self.supported_nets:
                    self.supported_nets.append(net)
        log(f" Fetched supported nets from APIs: {self.supported_nets}")

    def balance_accounts(self):
        balances = {name: exchange.get_balance(self.stable) for name, exchange in self.exchanges.items()}
        avg = sum(balances.values()) / Decimal(len(balances))
        for name, bal in balances.items():
            if bal < avg * Decimal('0.9'):
                from_name = max(balances, key=balances.get)
                amount = (avg - bal) / Decimal('2')
                best_fee, best_net, best_speed = self.get_best_net(from_name, name, amount)
                if best_fee is None:
                    log(f"No suitable net for transfer {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name}")
                    continue
                log(f"Best net: {best_net} (fee {best_fee.quantize(Decimal('0.00'))}, speed {best_speed}s)")
                if self.auto:
                    self.exchanges[from_name].withdraw(self.stable, str(amount), self.exchanges[name].fetch_deposit_address(self.stable)['address'], {'network': best_net})
                    log(f"AUTO X TRANSFER {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name} via {best_net}")
                else:
                    log(f"MANUAL X TRANSFER NEEDED!! : {amount.quantize(Decimal('0.00'))} {self.stable} from {from_name} to {name} via {best_net}, fee {best_fee.quantize(Decimal('0.00'))}")

    def get_best_net(self, from_name, to_name, amount: Decimal):
        fees = self.exchanges[from_name].fetch_deposit_withdraw_fees([self.stable])
        nets = fees[self.stable]['networks']
        candidates = []
        for net in self.supported_nets:
            if net in nets:
                fee = nets[net]['withdraw']['fee']
                speed = self.health.latency_metrics[from_name][-1] if self.health.latency_metrics[from_name] else Decimal('10')
                if net == 'ERC20' and amount < Decimal('10000'):
                    continue
                score = fee + (speed * Decimal('0.1'))
                candidates.append((fee, net, speed, score))
        if not candidates:
            return None, None, None
        best = min(candidates, key=lambda x: x[3])
        return best[0], best[1], best[2]

    def get_transfer_fee(self, from_name, to_name):
        fees = self.exchanges[from_name].fetch_deposit_withdraw_fees([self.stable])
        nets = fees[self.stable]['networks']
        best_net = min(nets, key=lambda n: nets[n]['withdraw']['fee'])
        return nets[best_net]['withdraw']['fee'], best_net

    def transfer(self, asset, from_name, to_name, amount: Decimal):
        if self.auto:
            net = self.get_best_net(from_name, to_name, amount)[1]
            address = self.exchanges[to_name].fetch_deposit_address(asset)['address']
            self.exchanges[from_name].withdraw(asset, amount, address, {'network': net})