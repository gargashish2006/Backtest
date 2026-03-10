from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple, Literal
import math


# -------------------------
# Canonical market data type
# -------------------------


@dataclass(frozen=True)
class Bar:
    ts: Any  # ideally: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# -------------------------
# Orders and fills
# -------------------------


SizingMode = Literal["qty", "target_weight"]


@dataclass(frozen=True)
class Order:
    """Market order specified in quantity (units/shares/contracts)."""

    ts: Any
    symbol: str
    side: str  # "BUY" | "SELL"
    qty: float
    order_type: str = "MARKET"  # MARKET (extend to LIMIT later)
    limit_price: Optional[float] = None


@dataclass(frozen=True)
class TargetWeightOrder:
    """Order expressed as a target portfolio weight for a symbol.

    The engine converts this into a delta-quantity market order based on
    current equity and the latest price.
    """

    ts: Any
    symbol: str
    target_weight: float  # -1.0..+1.0 (allow shorting if you want)


@dataclass(frozen=True)
class Fill:
    ts: Any
    symbol: str
    side: str
    qty: float
    price: float
    commission: float = 0.0


# -------------------------
# Portfolio types
# -------------------------


@dataclass
class Position:
    qty: float = 0.0
    avg_price: float = 0.0


@dataclass(frozen=True)
class PortfolioSnapshot:
    ts: Any
    cash: float
    equity: float
    positions: Dict[str, Position]


@dataclass(frozen=True)
class BacktestResult:
    snapshots: List[PortfolioSnapshot]
    fills: List[Fill]

    def equity_curve(self) -> List[Tuple[Any, float]]:
        return [(s.ts, s.equity) for s in self.snapshots]


# -------------------------
# Interfaces (strategy + data)
# -------------------------


class DataFeed(Protocol):
    """Yields (timestamp, [bars...]) where all bars share the same ts."""

    def __iter__(self) -> Iterable[Tuple[Any, Sequence[Bar]]]:
        ...


class Strategy(Protocol):
    def on_start(self, symbols: Sequence[str], initial_cash: float) -> None:
        ...

    def on_bar(self, ts: Any, bars: Sequence[Bar], portfolio: "Portfolio") -> Sequence[object]:
        """Return a list of Order or TargetWeightOrder."""

        ...

    def on_finish(self) -> None:
        ...


# -------------------------
# Execution model (slippage + commission)
# -------------------------


class ExecutionModel(Protocol):
    def fill_price(self, order: Order, bar: Bar) -> float:
        ...

    def commission(self, order: Order, fill_price: float) -> float:
        ...


@dataclass
class FixedBpsExecutionModel:
    """Deterministic execution model.

    - Slippage in bps of mid (bar.close)
    - Commission in bps of notional
    """

    slippage_bps: float = 5.0
    commission_bps: float = 2.0

    def fill_price(self, order: Order, bar: Bar) -> float:
        mid = float(bar.close)
        slip = (self.slippage_bps / 10_000.0) * mid
        return mid + slip if order.side.upper() == "BUY" else mid - slip

    def commission(self, order: Order, fill_price: float) -> float:
        notional = abs(order.qty) * fill_price
        return (self.commission_bps / 10_000.0) * notional


# -------------------------
# Portfolio/accounting
# -------------------------


@dataclass
class Portfolio:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)

    def get_position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position())

    def apply_fill(self, fill: Fill) -> None:
        pos = self.get_position(fill.symbol)
        signed_qty = fill.qty if fill.side.upper() == "BUY" else -fill.qty

        self.cash -= signed_qty * fill.price
        self.cash -= fill.commission

        new_qty = pos.qty + signed_qty
        if math.isclose(new_qty, 0.0, abs_tol=1e-12):
            pos.qty = 0.0
            pos.avg_price = 0.0
            return

        same_direction = (pos.qty >= 0 and signed_qty >= 0) or (pos.qty <= 0 and signed_qty <= 0)
        if same_direction:
            old_notional = pos.qty * pos.avg_price
            add_notional = signed_qty * fill.price
            pos.qty = new_qty
            pos.avg_price = (old_notional + add_notional) / new_qty
        else:
            pos.qty = new_qty
            # If position flips direction, reset avg price to fill.
            if (pos.qty > 0 and signed_qty > 0) or (pos.qty < 0 and signed_qty < 0):
                pos.avg_price = fill.price

    def equity(self, last_prices: Dict[str, float]) -> float:
        eq = self.cash
        for sym, pos in self.positions.items():
            px = last_prices.get(sym)
            if px is not None:
                eq += pos.qty * px
        return eq


# -------------------------
# Backtest engine
# -------------------------


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    execution: ExecutionModel = field(default_factory=FixedBpsExecutionModel)
    sizing_mode: SizingMode = "qty"
    # For target-weight sizing: if True, interpret target weights as final desired weights,
    # and expect the strategy to emit TargetWeightOrder objects.
    # If False, strategy emits qty Orders.


class BacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.results: Optional[BacktestResult] = None

    def _orders_from_target_weights(
        self,
        *,
        ts: Any,
        bars: Sequence[Bar],
        portfolio: Portfolio,
        last_prices: Dict[str, float],
        targets: Sequence[TargetWeightOrder],
    ) -> List[Order]:
        """Convert target weights into delta-quantity market orders.

        This does *delta rebalancing*: it computes current weight and trades the
        difference towards the target.
        """

        bar_by_symbol = {b.symbol: b for b in bars}
        equity = portfolio.equity(last_prices)
        if equity <= 0:
            return []

        orders: List[Order] = []
        for t in targets:
            bar = bar_by_symbol.get(t.symbol)
            if bar is None:
                continue

            px = float(last_prices.get(t.symbol, bar.close))
            if px <= 0:
                continue

            current_qty = portfolio.get_position(t.symbol).qty
            current_value = current_qty * px
            target_value = float(t.target_weight) * equity
            delta_value = target_value - current_value

            delta_qty = delta_value / px
            # Ignore tiny trades
            if abs(delta_qty) < 1e-6:
                continue

            side = "BUY" if delta_qty > 0 else "SELL"
            orders.append(
                Order(
                    ts=ts,
                    symbol=t.symbol,
                    side=side,
                    qty=abs(delta_qty),
                    order_type="MARKET",
                )
            )

        return orders

    def run_backtest(self, strategy: Strategy, data: DataFeed) -> BacktestResult:
        portfolio = Portfolio(cash=self.config.initial_cash)
        snapshots: List[PortfolioSnapshot] = []
        fills: List[Fill] = []
        last_prices: Dict[str, float] = {}

        started = False
        symbols: set[str] = set()

        for ts, bars in data:
            if not bars:
                continue

            if not started:
                for b in bars:
                    symbols.add(b.symbol)
                strategy.on_start(sorted(symbols), self.config.initial_cash)
                started = True

            # Update last prices
            for b in bars:
                last_prices[b.symbol] = float(b.close)

            # Strategy outputs orders
            raw_orders = list(strategy.on_bar(ts, bars, portfolio))

            # Normalize order types depending on sizing mode
            if self.config.sizing_mode == "target_weight":
                targets = [o for o in raw_orders if isinstance(o, TargetWeightOrder)]
                orders = self._orders_from_target_weights(
                    ts=ts,
                    bars=bars,
                    portfolio=portfolio,
                    last_prices=last_prices,
                    targets=targets,
                )
            else:
                orders = [o for o in raw_orders if isinstance(o, Order)]

            # Execute orders
            bar_by_symbol = {b.symbol: b for b in bars}
            for o in orders:
                b = bar_by_symbol.get(o.symbol)
                if b is None:
                    continue

                fill_px = self.config.execution.fill_price(o, b)
                comm = self.config.execution.commission(o, fill_px)
                fill = Fill(
                    ts=ts,
                    symbol=o.symbol,
                    side=o.side,
                    qty=float(o.qty),
                    price=float(fill_px),
                    commission=float(comm),
                )
                portfolio.apply_fill(fill)
                fills.append(fill)

            snapshots.append(
                PortfolioSnapshot(
                    ts=ts,
                    cash=float(portfolio.cash),
                    equity=float(portfolio.equity(last_prices)),
                    positions={s: Position(p.qty, p.avg_price) for s, p in portfolio.positions.items()},
                )
            )

        if started:
            strategy.on_finish()

        self.results = BacktestResult(snapshots=snapshots, fills=fills)
        return self.results

    def get_results(self) -> Optional[BacktestResult]:
        return self.results