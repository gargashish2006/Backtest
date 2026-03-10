from __future__ import annotations

import math

from backtesting.metrics import (
    adx,
    distance_from_52w_high,
    distance_from_high,
    ema,
    percentile_position,
    percentile_position_last_n_years,
    rsi,
    sma,
)


def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0
    assert sma([1, 2, 3, 4, 5], 3) == 4.0
    assert sma([1, 2], 3) is None


def test_ema_basic_increasing_series():
    # For a monotonic increasing series, EMA should be between last value and SMA.
    values = list(range(1, 21))
    e = ema(values, 10)
    assert e is not None
    assert e < values[-1]
    assert e > values[0]


def test_rsi_bounds_and_trends():
    up = list(range(1, 40))
    down = list(range(40, 0, -1))

    r_up = rsi(up, 14)
    r_down = rsi(down, 14)

    assert r_up is not None and 50 < r_up <= 100
    assert r_down is not None and 0 <= r_down < 50


def test_distance_from_high():
    # current is 20% below high
    vals = [10, 12, 15, 20, 16]
    d = distance_from_high(vals, 5)
    assert d is not None
    assert math.isclose(d, (16 - 20) / 20)


def test_distance_from_52w_high_wrapper():
    closes = [1.0] * 300
    closes[-1] = 0.9
    d = distance_from_52w_high(closes, trading_days_per_year=252)
    assert d is not None
    assert d < 0


def test_percentile_position_rank():
    vals = [10, 20, 30, 40, 50]
    assert math.isclose(percentile_position(vals, 5, method="rank"), 1.0)

    vals2 = [10, 20, 30, 40, 25]  # last value has rank 3/5
    assert math.isclose(percentile_position(vals2, 5, method="rank"), 3 / 5)


def test_percentile_position_minmax_constant_window():
    vals = [5, 5, 5, 5, 5]
    assert percentile_position(vals, 5, method="minmax") == 0.5


def test_percentile_position_last_n_years():
    closes = list(range(1, 505))
    p = percentile_position_last_n_years(closes, 1.0, trading_days_per_year=252)
    assert p is not None
    assert 0.9 < p <= 1.0


def test_adx_smoke_trending():
    # A gently trending series should produce a finite ADX value.
    n = 80
    closes = [100 + i * 0.2 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]

    a = adx(highs, lows, closes, period=14)
    assert a is not None
    assert 0 <= a <= 100
