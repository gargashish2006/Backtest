from __future__ import annotations

from backtesting.engine import BacktestConfig, BacktestEngine, Bar
from data.feeds.in_memory import InMemoryGroupedBarFeed
from strategies.examples import BuyAndHoldTwoAssets, EqualWeightRebalanceStrategy


def test_multi_security_qty_mode_runs() -> None:
    feed = InMemoryGroupedBarFeed(
        [
            (1, [Bar(1, "A", 100, 100, 100, 100), Bar(1, "B", 200, 200, 200, 200)]),
            (2, [Bar(2, "A", 110, 110, 110, 110), Bar(2, "B", 190, 190, 190, 190)]),
        ]
    )

    engine = BacktestEngine(BacktestConfig(initial_cash=10_000, sizing_mode="qty"))
    result = engine.run_backtest(BuyAndHoldTwoAssets(qty_per_symbol=1), feed)

    # Should hold 1 share of each
    last_positions = result.snapshots[-1].positions
    assert last_positions["A"].qty == 1
    assert last_positions["B"].qty == 1

    # Equity should reflect price changes
    # Starting equity ~ 10k - buy costs (with small commission/slippage) + MTM
    assert result.snapshots[-1].equity > 0


def test_multi_security_target_weight_mode_runs() -> None:
    feed = InMemoryGroupedBarFeed(
        [
            (1, [Bar(1, "A", 100, 100, 100, 100), Bar(1, "B", 100, 100, 100, 100)]),
            (2, [Bar(2, "A", 100, 100, 100, 100), Bar(2, "B", 100, 100, 100, 100)]),
        ]
    )

    engine = BacktestEngine(BacktestConfig(initial_cash=10_000, sizing_mode="target_weight"))
    result = engine.run_backtest(EqualWeightRebalanceStrategy(), feed)

    # Should create positions in both symbols
    last_positions = result.snapshots[-1].positions
    assert "A" in last_positions and "B" in last_positions
    assert last_positions["A"].qty != 0
    assert last_positions["B"].qty != 0
