from __future__ import annotations

from datetime import date

import pytest

from src.data.providers.dhan_provider import DhanAuth, DhanClient


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_dhan_provider_array_response_parsing(monkeypatch):
    client = DhanClient(DhanAuth(client_id="x", access_token="y"), base_url="https://api.dhan.co")

    def _fake_post(url, json, timeout):
        assert url.endswith("/v2/charts/historical")
        assert json["securityId"] == "2885"
        assert json["exchangeSegment"] == "NSE_EQ"
        assert json["instrument"] == "EQUITY"
        assert json["expiryCode"] == 0
        return _Resp(
            {
                "open": [1.0, 2.0],
                "high": [1.5, 2.5],
                "low": [0.5, 1.5],
                "close": [1.2, 2.2],
                "volume": [100.0, 200.0],
                "timestamp": [1704047400.0, 1704133800.0],
            }
        )

    monkeypatch.setattr(client.session, "post", _fake_post)

    rows = client.historical_daily(
        security_id="2885",
        exchange_segment="NSE_EQ",
        instrument="EQUITY",
        expiry_code=0,
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 10),
    )

    assert len(rows) == 2
    assert rows[0]["timestamp"] == 1704047400.0
    assert rows[0]["open"] == 1.0
    assert rows[1]["close"] == 2.2
