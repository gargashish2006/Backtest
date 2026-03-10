import datetime
import numpy as np
from backtesting.engine import Bar

def generate_dummy_bars(symbol: str, start: datetime.date, end: datetime.date, seed: int = 42) -> list[Bar]:
    np.random.seed(seed)
    days = (end - start).days + 1
    prices = [100.0]
    for _ in range(days - 1):
        # Simulate log returns with drift and volatility
        ret = np.random.normal(0.0003, 0.015)
        prices.append(prices[-1] * np.exp(ret))
    bars = []
    for i, px in enumerate(prices):
        dt = start + datetime.timedelta(days=i)
        if dt.weekday() >= 5:
            continue  # skip weekends
        open_ = px * np.random.uniform(0.995, 1.005)
        close = px
        high = max(open_, close) * np.random.uniform(1.0, 1.01)
        low = min(open_, close) * np.random.uniform(0.99, 1.0)
        volume = np.random.randint(1000, 5000)
        bars.append(Bar(ts=dt, symbol=symbol, open=open_, high=high, low=low, close=close, volume=volume))
    return bars

def generate_two_security_bars():
    start = datetime.date.today() - datetime.timedelta(days=365*5)
    end = datetime.date.today()
    bars1 = generate_dummy_bars("AAA", start, end, seed=42)
    bars2 = generate_dummy_bars("BBB", start, end, seed=99)
    return bars1 + bars2
