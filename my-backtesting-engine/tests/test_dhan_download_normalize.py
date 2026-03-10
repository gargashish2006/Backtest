from __future__ import annotations

from src.data.providers.dhan_download_daily import _normalize_candle


def test_normalize_candle_common_shape():
    raw = {"date": "2024-01-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}
    out = _normalize_candle(raw)
    assert out["date"] == "2024-01-01"
    assert out["open"] == 1.0
    assert out["high"] == 2.0
    assert out["low"] == 0.5
    assert out["close"] == 1.5
    assert out["volume"] == 100.0


def test_normalize_candle_short_keys():
    # 2024-01-01 00:00:00 UTC
    raw = {"timestamp": 1704067200.0, "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "1000"}
    out = _normalize_candle(raw)
    assert out["date"] == "2024-01-01"
    assert out["close"] == 10.5
