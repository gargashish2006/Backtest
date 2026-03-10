from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


# -------------------------
# Performance metrics
# -------------------------


def calculate_sharpe_ratio(returns, risk_free_rate: float = 0.0, annualization_factor: int = 252) -> float:
    """Compute annualized Sharpe ratio.

    Notes:
    - `returns` is assumed to be a numpy array / pandas Series of *period returns*.
    - If std is 0 or returns is empty, returns 0.
    """

    if len(returns) == 0:
        return 0.0
    excess_returns = returns - risk_free_rate
    std = excess_returns.std()
    if std == 0 or std != std:  # std != std checks NaN
        return 0.0
    return float(excess_returns.mean() / std * (annualization_factor**0.5))


def calculate_max_drawdown(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
    return float(max_drawdown)


# -------------------------
# Technical indicators (strategy inputs)
# -------------------------


def sma(values: Sequence[float], period: int) -> Optional[float]:
    """Simple moving average of the last `period` values."""
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) < period:
        return None
    window = values[-period:]
    return float(sum(window) / period)


def ema(values: Sequence[float], period: int) -> Optional[float]:
    """Exponential moving average (EMA).

    Returns EMA of full series, seeded with SMA(period) when possible.
    """
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    # Seed EMA with SMA of first `period` samples
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = alpha * v + (1 - alpha) * ema_val
    return float(ema_val)


def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """Relative Strength Index (RSI) using Wilder's smoothing."""
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(closes) < period + 1:
        return None

    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Wilder smoothing on remaining deltas
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Optional[float]:
    """Average Directional Index (ADX) using Wilder's method.

    Input series must be aligned and same length.
    """
    if period <= 0:
        raise ValueError("period must be > 0")
    n = len(closes)
    if len(highs) != n or len(lows) != n:
        raise ValueError("highs, lows, closes must be same length")
    if n < 2 * period + 1:
        # Typical ADX needs at least ~2*period to stabilize: TR/DM smoothing + DX smoothing
        return None

    tr: List[float] = []
    plus_dm: List[float] = []
    minus_dm: List[float] = []

    for i in range(1, n):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]

        tr_val = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        tr.append(tr_val)

        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)

    # Wilder smoothing of TR and DM
    tr14 = sum(tr[:period])
    plus_dm14 = sum(plus_dm[:period])
    minus_dm14 = sum(minus_dm[:period])

    dx: List[float] = []

    for i in range(period, len(tr)):
        if i > period:
            tr14 = tr14 - (tr14 / period) + tr[i]
            plus_dm14 = plus_dm14 - (plus_dm14 / period) + plus_dm[i]
            minus_dm14 = minus_dm14 - (minus_dm14 / period) + minus_dm[i]

        if tr14 == 0:
            dx.append(0.0)
            continue

        plus_di = 100 * (plus_dm14 / tr14)
        minus_di = 100 * (minus_dm14 / tr14)
        denom = plus_di + minus_di
        if denom == 0:
            dx.append(0.0)
        else:
            dx.append(100 * abs(plus_di - minus_di) / denom)

    # ADX is Wilder-smoothed DX
    adx_val = sum(dx[:period]) / period
    for i in range(period, len(dx)):
        adx_val = (adx_val * (period - 1) + dx[i]) / period

    return float(adx_val)


def distance_from_high(values: Sequence[float], lookback: int) -> Optional[float]:
    """Distance from the highest value in the last `lookback` samples.

    Returns a fraction:
      (current - max) / max
    Example:
      -0.10 means current is 10% below the lookback high.
    """
    if lookback <= 0:
        raise ValueError("lookback must be > 0")
    if len(values) < lookback:
        return None
    window = values[-lookback:]
    high = max(window)
    if high == 0:
        return None
    return float((values[-1] - high) / high)


def distance_from_52w_high(
    closes: Sequence[float],
    trading_days_per_year: int = 252,
) -> Optional[float]:
    """Convenience wrapper: distance from 52-week high using trading days."""

    return distance_from_high(closes, lookback=trading_days_per_year)


def percentile_position(
    values: Sequence[float],
    lookback: int,
    *,
    method: str = "rank",
) -> Optional[float]:
    """Percentile position of the latest value within the last `lookback` samples.

    Returns a float in [0, 1].

    Methods:
    - "rank": rank-based percentile using <= comparisons (robust to outliers)
    - "minmax": (x - min) / (max - min)
    """
    if lookback <= 1:
        raise ValueError("lookback must be > 1")
    if len(values) < lookback:
        return None
    window = list(values[-lookback:])
    x = window[-1]

    if method == "minmax":
        lo = min(window)
        hi = max(window)
        if hi == lo:
            return 0.5
        return float((x - lo) / (hi - lo))

    if method == "rank":
        # rank percentile: proportion of points <= x
        count = sum(1 for v in window if v <= x)
        return float(count / len(window))

    raise ValueError("method must be 'rank' or 'minmax'")


def percentile_position_last_n_years(
    closes: Sequence[float],
    n_years: float,
    *,
    trading_days_per_year: int = 252,
    method: str = "rank",
) -> Optional[float]:
    """Convenience wrapper: percentile position within last N years.

    Uses trading days approximation.
    """
    lookback = int(round(n_years * trading_days_per_year))
    return percentile_position(closes, lookback=lookback, method=method)