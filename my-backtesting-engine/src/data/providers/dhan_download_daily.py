from __future__ import annotations

"""Download Dhan daily OHLCV into a single combined Parquet file.

Output schema (one row per symbol per date):
- date (YYYY-MM-DD)
- symbol
- exchange_segment (e.g. NSE_EQ, BSE_EQ)
- instrument (EQUITY, INDEX)
- expiry_code (0 for spot; used for some derivative instruments)
- open/high/low/close/volume

Inputs:
- An instruments mapping parquet/csv file containing at least:
        symbol, exchange_segment, instrument, security_id
    Optional:
        expiry_code

Environment variables:
- DHAN_CLIENT_ID
- DHAN_ACCESS_TOKEN
- (optional) DHAN_BASE_URL

Example:
    python -m src.data.providers.dhan_download_daily \
      --instruments ./instruments/dhan_instruments.csv \
      --start 2020-01-01 --end 2026-01-27 \
      --out ./data/dhan_daily_all.parquet \
      --chunk-days 180 --retries 3

Retry failures:
    python -m src.data.providers.dhan_download_daily \
      --instruments ./data/dhan_daily_all.failures.csv \
      --start 2020-01-01 --end 2026-01-27 \
      --out ./data/dhan_daily_all.parquet \
      --retry-failures

Notes:
- This module keeps the write-side simple. We can add resume/checkpointing later.
- Requires: pandas + pyarrow (for parquet).
"""

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import pandas as pd

from .dhan_provider import DhanClient, get_dhan_auth_from_env


@dataclass(frozen=True)
class InstrumentRow:
    symbol: str
    exchange_segment: str
    instrument: str
    security_id: str
    expiry_code: int = 0


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


_TRAILING_DOT_ZERO_RE = re.compile(r"\.0$")
_SECURITY_ID_DIGITS_RE = re.compile(r"^\d+$")


def _normalize_security_id(value: Any) -> str:
    """Coerce securityId into a clean string (e.g. '16921', not '16921.0')."""
    if value is None:
        return ""

    # pandas may give numpy scalar types.
    try:
        if pd.isna(value):
            return ""
    except Exception:  # noqa: BLE001
        pass

    # Numeric types
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        # if it looks like an integer float, drop decimals
        if value.is_integer():
            return str(int(value))
        return str(value)

    s = str(value).strip()
    s = _TRAILING_DOT_ZERO_RE.sub("", s)
    # Some CSVs may accidentally have scientific notation.
    # If it's a float-like string but integral, coerce to int-string.
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except Exception:  # noqa: BLE001
        pass
    return s


def _is_valid_security_id(security_id: str) -> bool:
    return bool(security_id) and bool(_SECURITY_ID_DIGITS_RE.match(security_id))


def _read_instruments(path: Path) -> List[InstrumentRow]:
    if not path.exists():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    required = {"symbol", "exchange_segment", "instrument", "security_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Instruments file missing columns: {sorted(missing)}")

    out: List[InstrumentRow] = []
    for _, r in df.iterrows():
        expiry_code = int(r["expiry_code"]) if "expiry_code" in df.columns and pd.notna(r["expiry_code"]) else 0
        out.append(
            InstrumentRow(
                symbol=str(r["symbol"]).strip(),
                exchange_segment=str(r["exchange_segment"]).strip().upper(),
                instrument=str(r["instrument"]).strip().upper(),
                security_id=_normalize_security_id(r["security_id"]),
                expiry_code=expiry_code,
            )
        )
    return out


def _normalize_candle(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort normalization. Update mapping once Dhan response is confirmed."""

    d = raw.get("date") or raw.get("ts") or raw.get("timestamp")
    if isinstance(d, (int, float)):
        d = datetime.fromtimestamp(int(d), tz=timezone.utc).date().isoformat()
    elif hasattr(d, "date"):
        # datetime
        d = d.date().isoformat()
    elif hasattr(d, "isoformat"):
        d = d.isoformat()

    return {
        "date": str(d),
        "open": float(raw.get("open") or raw.get("o")),
        "high": float(raw.get("high") or raw.get("h")),
        "low": float(raw.get("low") or raw.get("l")),
        "close": float(raw.get("close") or raw.get("c")),
        "volume": float(raw.get("volume") or raw.get("v") or 0.0),
    }


_SECURITY_ID_DIGITS_RE = re.compile(r"^\d+$")


def _is_valid_security_id(security_id: str) -> bool:
    return bool(security_id) and bool(_SECURITY_ID_DIGITS_RE.match(security_id))


def _date_chunks(start: date, end: date, chunk_days: int) -> Iterable[Tuple[date, date]]:
    """Yield inclusive [chunk_start, chunk_end] ranges."""
    if chunk_days <= 0:
        yield start, end
        return

    cur = start
    while cur <= end:
        chunk_end = min(end, cur + timedelta(days=chunk_days - 1))
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


_LOCK = threading.Lock()


def _sleep_backoff(attempt: int, *, base_s: float = 0.75, cap_s: float = 15.0) -> None:
    delay = min(cap_s, base_s * (2 ** max(0, attempt - 1)))
    time.sleep(delay)


def _merge_parquet_files(original: Path, new_data: Path, output: Path) -> None:
    """
    Merge two parquet files and deduplicate by (date, symbol, exchange_segment, instrument, expiry_code).
    Writes result to output path.
    """
    df_old = pd.read_parquet(original)
    df_new = pd.read_parquet(new_data)
    
    df_combined = pd.concat([df_old, df_new], ignore_index=True)
    
    # Deduplicate on the full key
    df_combined = df_combined.drop_duplicates(
        subset=["date", "symbol", "exchange_segment", "instrument", "expiry_code"],
        keep="last"
    )
    
    # Sort for consistency
    df_combined = df_combined.sort_values(["symbol", "exchange_segment", "date"]).reset_index(drop=True)
    
    df_combined.to_parquet(output, index=False)
    print(f"Merged: {len(df_old):,} (old) + {len(df_new):,} (new) → {len(df_combined):,} (deduplicated)")


def download_all(
    *,
    instruments: List[InstrumentRow],
    start: date,
    end: date,
    out_path: Path,
    base_url: Optional[str] = None,
    sleep_s: float = 0.25,
    chunk_days: int = 180,
    retries: int = 3,
    limit: Optional[int] = None,
    stop_on_error: bool = False,
    workers: int = 1,
) -> None:
    auth = get_dhan_auth_from_env()
    client = DhanClient(auth, base_url=base_url)

    all_rows: List[Dict[str, Any]] = []
    all_failures: List[Dict[str, Any]] = []
    instruments_to_run = instruments[:limit] if limit else instruments
    total = len(instruments_to_run)

    def process_instrument(idx: int, inst: InstrumentRow) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        inst_rows = []
        inst_failures = []
        if not _is_valid_security_id(inst.security_id):
            inst_failures.append(
                {
                    "symbol": inst.symbol,
                    "security_id": inst.security_id,
                    "exchange_segment": inst.exchange_segment,
                    "instrument": inst.instrument,
                    "expiry_code": inst.expiry_code,
                    "error_code": "INVALID_SECURITY_ID",
                    "error_message": "security_id must be digits",
                }
            )
            print(
                f"[{idx}/{total}] {inst.exchange_segment} {inst.instrument} {inst.symbol}: SKIP invalid security_id={inst.security_id!r}"
            )
            return inst_rows, inst_failures

        try:
            per_symbol_count = 0
            for c_start, c_end in _date_chunks(start, end, chunk_days):
                attempt = 1
                while True:
                    try:
                        raw = client.historical_daily(
                            security_id=inst.security_id,
                            exchange_segment=inst.exchange_segment,
                            instrument=inst.instrument,
                            expiry_code=inst.expiry_code,
                            from_date=c_start,
                            to_date=c_end,
                        )
                        if not raw:
                            inst_failures.append(
                                {
                                    "symbol": inst.symbol,
                                    "security_id": inst.security_id,
                                    "exchange_segment": inst.exchange_segment,
                                    "instrument": inst.instrument,
                                    "expiry_code": inst.expiry_code,
                                    "fromDate": c_start.isoformat(),
                                    "toDate": c_end.isoformat(),
                                    "error_code": "NO_DATA",
                                    "error_message": "Empty response for date window",
                                }
                            )
                            break

                        norm = [_normalize_candle(r) for r in raw]
                        for r in norm:
                            r["symbol"] = inst.symbol
                            r["exchange_segment"] = inst.exchange_segment
                            r["instrument"] = inst.instrument
                            r["expiry_code"] = inst.expiry_code
                        inst_rows.extend(norm)
                        per_symbol_count += len(norm)
                        break
                    except Exception as e:
                        msg = str(e)
                        if "DH-905" in msg and "no data" in msg.lower():
                            inst_failures.append(
                                {
                                    "symbol": inst.symbol,
                                    "security_id": inst.security_id,
                                    "exchange_segment": inst.exchange_segment,
                                    "instrument": inst.instrument,
                                    "expiry_code": inst.expiry_code,
                                    "fromDate": c_start.isoformat(),
                                    "toDate": c_end.isoformat(),
                                    "error_code": "DH-905",
                                    "error_message": msg,
                                }
                            )
                            break
                        
                        if "Rate_Limit" in msg or "DH-904" in msg or "429" in msg:
                             print(f"Rate limit hit for {inst.symbol}. Sleeping 10s...")
                             time.sleep(10)

                        if attempt >= retries:
                            inst_failures.append(
                                {
                                    "symbol": inst.symbol,
                                    "security_id": inst.security_id,
                                    "exchange_segment": inst.exchange_segment,
                                    "instrument": inst.instrument,
                                    "expiry_code": inst.expiry_code,
                                    "fromDate": c_start.isoformat(),
                                    "toDate": c_end.isoformat(),
                                    "error_code": "HTTP_ERROR",
                                    "error_message": str(e),
                                }
                            )
                            raise StopIteration
                        _sleep_backoff(attempt)
                        attempt += 1

                if sleep_s > 0:
                    time.sleep(sleep_s)

            print(f"[{idx}/{total}] {inst.exchange_segment} {inst.instrument} {inst.symbol}: {per_symbol_count} rows")
        except StopIteration:
            last_err = inst_failures[-1]['error_message'] if inst_failures else "Unknown error"
            print(f"[{idx}/{total}] {inst.exchange_segment} {inst.instrument} {inst.symbol}: ERROR (skipped after retries): {last_err}")
        except Exception as e:
            print(f"[{idx}/{total}] {inst.exchange_segment} {inst.instrument} {inst.symbol}: ERROR: {e}")
        
        return inst_rows, inst_failures

    if workers > 1:
        print(f"Starting parallel download with {workers} workers...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_instrument, i, inst) for i, inst in enumerate(instruments_to_run, start=1)]
            for future in as_completed(futures):
                rows, failures = future.result()
                all_rows.extend(rows)
                all_failures.extend(failures)
    else:
        for idx, inst in enumerate(instruments_to_run, start=1):
            rows, failures = process_instrument(idx, inst)
            all_rows.extend(rows)
            all_failures.extend(failures)

    if not all_rows:
        raise RuntimeError("No rows downloaded. Check credentials, instruments mapping, and endpoint config.")

    df = pd.DataFrame(all_rows)

    # Normalize dtypes
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop completely invalid dates
    df = df.dropna(subset=["open", "high", "low", "close"])

    # Deduplicate key rows (chunking can overlap at boundaries)
    df = df.drop_duplicates(subset=["date", "symbol", "exchange_segment", "instrument", "expiry_code"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"\nWrote {len(df):,} rows to {out_path}")

    if failures:
        failures_path = out_path.with_suffix(".failures.csv")
        pd.DataFrame(failures).to_csv(failures_path, index=False)
        print(f"Wrote {len(failures):,} failures to {failures_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Download Dhan daily OHLCV -> combined parquet")
    p.add_argument(
        "--instruments",
        required=True,
        help="CSV/Parquet with symbol,exchange_segment,instrument,security_id[,expiry_code]",
    )
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", required=True, help="Output parquet file")
    p.add_argument("--base-url", default=None, help="Override DHAN_BASE_URL")
    p.add_argument("--sleep", type=float, default=0.25, help="Sleep between symbols")
    p.add_argument(
        "--chunk-days",
        type=int,
        default=180,
        help="Split long date ranges into <=N day chunks per symbol (avoids API limits/timeouts).",
    )
    p.add_argument("--retries", type=int, default=3, help="Retries per chunk on transient failures")
    p.add_argument("--limit", type=int, default=None, help="Only process first N instruments (debugging)")
    p.add_argument("--stop-on-error", action="store_true", help="Stop immediately on first error")
    p.add_argument(
        "--retry-failures",
        action="store_true",
        help="Merge mode: download to temp file, then merge with existing --out parquet (deduplicating)",
    )
    p.add_argument("--workers", type=int, default=1, help="Number of parallel workers")
    args = p.parse_args()

    instruments = _read_instruments(Path(args.instruments))
    out_path = Path(args.out)

    # If retry-failures mode and output already exists, download to temp then merge
    if args.retry_failures and out_path.exists():
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            temp_path = Path(tmp.name)
        
        try:
            print(f"Retry-failures mode: downloading to temp file {temp_path}")
            download_all(
                instruments=instruments,
                start=_parse_date(args.start),
                end=_parse_date(args.end),
                out_path=temp_path,
                base_url=args.base_url,
                sleep_s=args.sleep,
                chunk_days=args.chunk_days,
                retries=args.retries,
                limit=args.limit,
                stop_on_error=args.stop_on_error,
                workers=args.workers,
            )
            
            print(f"\nMerging {temp_path} into {out_path}...")
            _merge_parquet_files(original=out_path, new_data=temp_path, output=out_path)
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
                print(f"Removed temp file {temp_path}")
    else:
        # Normal mode: download directly to output
        download_all(
            instruments=instruments,
            start=_parse_date(args.start),
            end=_parse_date(args.end),
            out_path=out_path,
            base_url=args.base_url,
            sleep_s=args.sleep,
            chunk_days=args.chunk_days,
            retries=args.retries,
            limit=args.limit,
            stop_on_error=args.stop_on_error,
            workers=args.workers,
        )



if __name__ == "__main__":
    main()
