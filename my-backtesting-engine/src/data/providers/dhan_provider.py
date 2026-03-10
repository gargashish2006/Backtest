from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import os
import time

import requests
from requests import Response


@dataclass(frozen=True)
class DhanAuth:
    client_id: str
    access_token: str


def get_dhan_auth_from_env() -> DhanAuth:
    """Read Dhan credentials from env vars.

    Required:
    - DHAN_CLIENT_ID
    - DHAN_ACCESS_TOKEN

    Base URL can be overridden via:
    - DHAN_BASE_URL
    """

    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        raise RuntimeError(
            "Missing Dhan credentials. Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN env vars."
        )
    return DhanAuth(client_id=client_id, access_token=access_token)


class DhanClient:
    """Thin HTTP client for Dhan historical daily OHLCV.

    This is intentionally minimal and keeps all Dhan-specific behavior isolated.
    You will likely need to update `historical_daily()` to the exact endpoint + payload
    based on the Dhan API docs you’re using.
    """

    def __init__(self, auth: DhanAuth, *, base_url: Optional[str] = None, timeout_s: int = 30):
        self.base_url = (base_url or os.getenv("DHAN_BASE_URL") or "https://api.dhan.co").rstrip("/")
        self.timeout_s = timeout_s
        self.session = requests.Session()

        # NOTE: Header names may differ depending on Dhan API. Update if needed.
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "client-id": auth.client_id,
                "access-token": auth.access_token,
            }
        )

    def historical_daily(
        self,
        *,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        expiry_code: int = 0,
        from_date: date,
        to_date: date,
        retries: int = 3,
        backoff_s: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Fetch historical daily candles.

        Expected output: list of dict rows, each containing date/open/high/low/close/volume.

        IMPORTANT: The endpoint/payload/response parsing here are placeholders.
        Once you confirm Dhan’s exact historical endpoint/shape, we’ll update this.
        """

        endpoint = f"{self.base_url}/v2/charts/historical"
        payload: Dict[str, Any] = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument,
            "expiryCode": int(expiry_code),
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }

        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp: Response = self.session.post(endpoint, json=payload, timeout=self.timeout_s)
                if resp.status_code >= 400:
                    # Dhan often sends actionable JSON with errorCode/message. Include it.
                    try:
                        details = resp.json()
                    except Exception:  # noqa: BLE001
                        details = resp.text
                    raise requests.HTTPError(
                        f"HTTP {resp.status_code} for {endpoint}. Payload={payload}. Response={details}",
                        response=resp,
                    )

                data = resp.json()

                # Dhan returns arrays keyed by field name.
                # {
                #   "open": [...], "high": [...], "low": [...], "close": [...],
                #   "volume": [...], "timestamp": [...]
                # }
                opens = data.get("open") or []
                highs = data.get("high") or []
                lows = data.get("low") or []
                closes = data.get("close") or []
                volumes = data.get("volume") or []
                ts = data.get("timestamp") or []

                if not (isinstance(opens, list) and isinstance(ts, list)):
                    raise ValueError(f"Unexpected historical response shape: {data}")

                n = min(len(ts), len(opens), len(highs), len(lows), len(closes), len(volumes))
                rows: List[Dict[str, Any]] = []
                for i in range(n):
                    rows.append(
                        {
                            "timestamp": ts[i],
                            "open": opens[i],
                            "high": highs[i] if i < len(highs) else None,
                            "low": lows[i] if i < len(lows) else None,
                            "close": closes[i] if i < len(closes) else None,
                            "volume": volumes[i] if i < len(volumes) else 0.0,
                        }
                    )
                return rows
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < retries - 1:
                    time.sleep(backoff_s * (2**attempt))
                else:
                    break

        assert last_err is not None
        raise last_err
