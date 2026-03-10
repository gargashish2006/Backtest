class SlippageModel:
    def __init__(self, slippage_percentage):
        self.slippage_percentage = slippage_percentage

    def apply_slippage(self, order):
        slippage_amount = order.price * self.slippage_percentage
        adjusted_price = order.price + slippage_amount
        order.price = adjusted_price
        return order