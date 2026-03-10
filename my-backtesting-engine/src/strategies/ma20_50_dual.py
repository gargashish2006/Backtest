from collections import deque
from typing import Sequence, List, Dict, Any
from backtesting.engine import Bar, Order, TargetWeightOrder, Portfolio

class MA20_50_Strategy:
    def __init__(self, sizing_mode: str = "target_weight"):
        self.sizing_mode = sizing_mode
        self.prices: Dict[str, deque] = {}
        self.ma20: Dict[str, float] = {}
        self.ma50: Dict[str, float] = {}
        self.holdings: Dict[str, bool] = {}
        self.symbols: List[str] = []

    def on_start(self, symbols: Sequence[str], initial_cash: float) -> None:
        self.symbols = list(symbols)
        for sym in symbols:
            self.prices[sym] = deque(maxlen=50)
            self.holdings[sym] = False
            self.ma20[sym] = 0.0
            self.ma50[sym] = 0.0

    def on_bar(self, ts: Any, bars: Sequence[Bar], portfolio: Portfolio) -> List[Any]:
        orders = []
        signals = {}
        for bar in bars:
            self.prices[bar.symbol].append(bar.close)
            if len(self.prices[bar.symbol]) >= 20:
                ma20 = sum(list(self.prices[bar.symbol])[-20:]) / 20
                self.ma20[bar.symbol] = ma20
            if len(self.prices[bar.symbol]) == 50:
                ma50 = sum(self.prices[bar.symbol]) / 50
                self.ma50[bar.symbol] = ma50
            # Signal logic
            if len(self.prices[bar.symbol]) >= 50:
                if self.ma20[bar.symbol] > self.ma50[bar.symbol]:
                    signals[bar.symbol] = "BUY"
                else:
                    signals[bar.symbol] = "SELL"
            else:
                signals[bar.symbol] = None

        # Portfolio allocation logic
        n_buy = sum(1 for s in signals.values() if s == "BUY")
        for sym in self.symbols:
            sig = signals[sym]
            if sig == "BUY":
                target_weight = 0.5 if n_buy == 1 else 0.5 / n_buy if n_buy > 0 else 0.0
                if self.sizing_mode == "target_weight":
                    orders.append(TargetWeightOrder(ts=ts, symbol=sym, target_weight=target_weight))
                else:
                    # For qty mode, compute qty to reach 50% allocation
                    # (handled by engine if using target_weight mode)
                    pass
            elif sig == "SELL" and portfolio.get_position(sym).qty > 0:
                if self.sizing_mode == "target_weight":
                    orders.append(TargetWeightOrder(ts=ts, symbol=sym, target_weight=0.0))
                else:
                    # For qty mode, sell all
                    qty = abs(portfolio.get_position(sym).qty)
                    if qty > 0:
                        orders.append(Order(ts=ts, symbol=sym, side="SELL", qty=qty))
        return orders

    def on_finish(self) -> None:
        pass
