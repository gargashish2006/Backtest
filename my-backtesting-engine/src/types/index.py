from enum import Enum

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class Trade:
    def __init__(self, symbol, quantity, price, order_type: OrderType):
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        self.timestamp = None  # To be set when the trade is executed

    def __repr__(self):
        return f"Trade(symbol={self.symbol}, quantity={self.quantity}, price={self.price}, order_type={self.order_type})"