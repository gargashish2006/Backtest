import sys
from pathlib import Path

# Ensure `src/` is importable when running this file directly.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtesting.engine import BacktestEngine, BacktestConfig
from data.in_memory_feed import InMemoryBarFeed
from data.generate_dummy_data import generate_two_security_bars
from strategies.ma20_50_dual import MA20_50_Strategy

if __name__ == "__main__":
    bars = generate_two_security_bars()
    feed = InMemoryBarFeed(bars)
    strategy = MA20_50_Strategy(sizing_mode="target_weight")
    config = BacktestConfig(initial_cash=100_000, sizing_mode="target_weight")
    engine = BacktestEngine(config)
    result = engine.run_backtest(strategy, feed)

    # Print equity curve summary
    eq_curve = result.equity_curve()
    print("Date,Equity")
    for dt, eq in eq_curve[-10:]:  # show last 10 days
        print(f"{dt},{eq:.2f}")
    print(f"\nFinal equity: {eq_curve[-1][1]:.2f}")
    print(f"Total trades: {len(result.fills)}")
    # Print last positions
    last_snap = result.snapshots[-1]
    print("\nFinal positions:")
    for sym, pos in last_snap.positions.items():
        print(f"{sym}: qty={pos.qty:.2f} avg_price={pos.avg_price:.2f}")
