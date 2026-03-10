class Portfolio:
    def __init__(self, initial_cash=100000):
        self.cash = initial_cash
        self.positions = {}
    
    def update_portfolio(self, positions):
        for symbol, amount in positions.items():
            if symbol in self.positions:
                self.positions[symbol] += amount
            else:
                self.positions[symbol] = amount
    
    def calculate_value(self, current_prices):
        total_value = self.cash
        for symbol, amount in self.positions.items():
            total_value += amount * current_prices.get(symbol, 0)
        return total_value