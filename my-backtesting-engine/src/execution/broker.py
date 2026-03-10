class Broker:
    def __init__(self, initial_balance=10000):
        self.balance = initial_balance
        self.positions = {}

    def execute_order(self, order):
        if order['type'] == 'buy':
            self._buy(order)
        elif order['type'] == 'sell':
            self._sell(order)

    def _buy(self, order):
        cost = order['price'] * order['quantity']
        if self.balance >= cost:
            self.balance -= cost
            self.positions[order['symbol']] = self.positions.get(order['symbol'], 0) + order['quantity']
        else:
            raise ValueError("Insufficient balance to execute buy order.")

    def _sell(self, order):
        if order['symbol'] in self.positions and self.positions[order['symbol']] >= order['quantity']:
            self.positions[order['symbol']] -= order['quantity']
            self.balance += order['price'] * order['quantity']
        else:
            raise ValueError("Insufficient position to execute sell order.")

    def get_balance(self):
        return self.balance

    def get_positions(self):
        return self.positions.copy()