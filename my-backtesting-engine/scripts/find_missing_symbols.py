"""
Generate a failures/missing instruments CSV by comparing:
- Input instruments file (what you requested)
- Output parquet (what you got)

Usage:
    python scripts/find_missing_symbols.py \
      --instruments ./dhan_instruments.csv \
      --parquet ./data/dhan_daily_full.parquet \
      --out ./data/dhan_daily_full.failures.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description="Find symbols missing from downloaded parquet")
    p.add_argument("--instruments", required=True, help="Original instruments CSV/Parquet")
    p.add_argument("--parquet", required=True, help="Downloaded data parquet")
    p.add_argument("--out", required=True, help="Output failures CSV")
    args = p.parse_args()

    instruments_path = Path(args.instruments)
    parquet_path = Path(args.parquet)
    out_path = Path(args.out)

    # Read instruments
    if instruments_path.suffix.lower() in {".parquet", ".pq"}:
        instruments_df = pd.read_parquet(instruments_path)
    else:
        instruments_df = pd.read_csv(instruments_path)

    # Read downloaded data
    data_df = pd.read_parquet(parquet_path)

    # Get unique symbols that were successfully downloaded
    downloaded_keys = set(
        data_df[["symbol", "exchange_segment", "instrument", "expiry_code"]]
        .drop_duplicates()
        .apply(
            lambda r: (
                str(r["symbol"]).strip().upper(),
                str(r["exchange_segment"]).strip().upper(),
                str(r["instrument"]).strip().upper(),
                int(r.get("expiry_code", 0) or 0),
            ),
            axis=1,
        )
    )

    # Find missing
    missing = []
    for _, row in instruments_df.iterrows():
        key = (
            str(row["symbol"]).strip().upper(),
            str(row["exchange_segment"]).strip().upper(),
            str(row["instrument"]).strip().upper(),
            int(row.get("expiry_code", 0) or 0),
        )
        if key not in downloaded_keys:
            missing.append(
                {
                    "symbol": row["symbol"],
                    "security_id": row["security_id"],
                    "exchange_segment": row["exchange_segment"],
                    "instrument": row["instrument"],
                    "expiry_code": row.get("expiry_code", 0),
                }
            )

    if not missing:
        print("✅ All instruments were successfully downloaded!")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(missing).to_csv(out_path, index=False)
    print(f"📝 Wrote {len(missing):,} missing instruments to {out_path}")
    print(f"\n📋 Summary:")
    print(f"   Requested: {len(instruments_df):,} instruments")
    print(f"   Downloaded: {len(downloaded_keys):,} instruments")
    print(f"   Missing: {len(missing):,} instruments")
    print(f"\n🔄 To retry these, run:")
    print(f"  python -m src.data.providers.dhan_download_daily \\")
    print(f"    --instruments {out_path} \\")
    print(f"    --start YYYY-MM-DD --end YYYY-MM-DD \\")
    print(f"    --out {parquet_path} \\")
    print(f"    --retry-failures")


if __name__ == "__main__":
    main()
