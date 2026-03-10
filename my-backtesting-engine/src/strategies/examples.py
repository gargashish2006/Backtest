from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, List

from backtesting.engine import Bar, Order, TargetWeightOrder, Portfolio


@dataclass
class EqualWeightRebalanceStrategy:
    """Rebalance to equal-weight across the symbols every bar.

    Intended for target-weight sizing mode.
    """

    def on_start(self, symbols: Sequence[str], initial_cash: float) -> None:
        self.symbols = list(symbols)

    def on_bar(self, ts: Any, bars: Sequence[Bar], portfolio: Portfolio) -> Sequence[object]:
        if not self.symbols:
            return []
        w = 1.0 / len(self.symbols)
        return [TargetWeightOrder(ts=ts, symbol=s, target_weight=w) for s in self.symbols]

    def on_finish(self) -> None:
        return


@dataclass
class BuyAndHoldTwoAssets:
    """Buy a fixed quantity of each symbol on the first bar, then hold.

    Intended for qty sizing mode.
    """

    qty_per_symbol: float = 1.0

    def on_start(self, symbols: Sequence[str], initial_cash: float) -> None:
        self.symbols = list(symbols)
        self.did_buy = False

    def on_bar(self, ts: Any, bars: Sequence[Bar], portfolio: Portfolio) -> Sequence[object]:
        if self.did_buy:
            return []
        self.did_buy = True
        orders: List[Order] = []
        for b in bars:
            orders.append(Order(ts=ts, symbol=b.symbol, side="BUY", qty=self.qty_per_symbol))
        return orders

    def on_finish(self) -> None:
        return
