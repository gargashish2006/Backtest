import unittest
from datetime import datetime, timedelta

from src.backtesting.engine import Bar, BacktestConfig, BacktestEngine
from src.data.in_memory_feed import InMemoryBarFeed
from src.strategies.base import Strategy

class TestBacktestEngine(unittest.TestCase):

    class MockStrategy(Strategy):
        # Legacy abstract methods (kept for compatibility in this repo)
        def generate_signals(self, data):
            return []

        def backtest(self, data):
            return self.generate_signals(data)

        # Event-driven hooks (used by our BacktestEngine)
        def on_start(self, *args, **kwargs):
            self.seen = 0

        def on_bar(self, ts, bars, portfolio):
            # No orders; just count bars.
            self.seen += len(bars)
            return []

        def on_finish(self, *args, **kwargs):
            pass

    def setUp(self):
        self.engine = BacktestEngine(BacktestConfig(initial_cash=100_000.0))
        start = datetime(2020, 1, 1)
        bars = [
            Bar(ts=start + timedelta(days=i), symbol="AAA", open=100 + i, high=101 + i, low=99 + i, close=100 + i, volume=1000)
            for i in range(10)
        ]
        self.data = InMemoryBarFeed(bars)
        self.strategy = self.MockStrategy()

    def test_run_backtest(self):
        results = self.engine.run_backtest(self.strategy, self.data)
        self.assertIsNotNone(results)
        self.assertGreaterEqual(len(results.snapshots), 1)

    def test_get_results(self):
        self.engine.run_backtest(self.strategy, self.data)
        results = self.engine.get_results()
        self.assertIsNotNone(results)
        self.assertGreaterEqual(len(results.snapshots), 1)

if __name__ == '__main__':
    unittest.main()