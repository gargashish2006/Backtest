import unittest
from src.strategies.base import Strategy

class TestSampleStrategy(Strategy):
    def generate_signals(self, data):
        # Sample implementation for testing
        return [1 if price > 100 else 0 for price in data]

    def backtest(self, data):
        signals = self.generate_signals(data)
        return signals

class TestStrategies(unittest.TestCase):
    def setUp(self):
        self.strategy = TestSampleStrategy()

    def test_generate_signals(self):
        data = [90, 110, 95, 105]
        expected_signals = [0, 1, 0, 1]
        signals = self.strategy.generate_signals(data)
        self.assertEqual(signals, expected_signals)

    def test_backtest(self):
        data = [90, 110, 95, 105]
        expected_signals = [0, 1, 0, 1]
        results = self.strategy.backtest(data)
        self.assertEqual(results, expected_signals)

if __name__ == '__main__':
    unittest.main()