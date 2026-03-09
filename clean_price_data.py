"""
Clean price_data.parquet: fix only true isolated single-day price spikes.
A true spike = day N has pct_change > +50% AND day N+1 has pct_change < -50%
(or vice versa). This pattern = bad data point, not a corporate action.
Corporate actions (splits/bonuses) cause a sustained level change, not an immediate reversal.

Fix: replace the spike day's close with the average of the prior and next day's close.
"""
import pandas as pd
import numpy as np
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
src = repo_root / "database/price_data.parquet"
dst = repo_root / "database/price_data_cleaned.parquet"

THRESHOLD = 0.50  # 50% single-day move

print(f"Loading {src}...")
df = pd.read_parquet(src)
print(f"Loaded {len(df):,} rows.")

df = df.sort_values(['isin', 'date']).reset_index(drop=True)

# Compute pct change and next-day pct change per stock
df['pct_chg']      = df.groupby('isin')['close'].pct_change()
df['next_pct_chg'] = df.groupby('isin')['close'].pct_change().shift(-1)

# True spike: large move on day N that fully reverses on day N+1
# Spike up then crash: pct_chg > +THRESHOLD and next_pct_chg < -THRESHOLD
# Spike down then recover: pct_chg < -THRESHOLD and next_pct_chg > +THRESHOLD
is_spike = (
    ((df['pct_chg'] > THRESHOLD) & (df['next_pct_chg'] < -THRESHOLD)) |
    ((df['pct_chg'] < -THRESHOLD) & (df['next_pct_chg'] > THRESHOLD))
)

spike_rows = df[is_spike].copy()
print(f"\nFound {len(spike_rows)} true isolated spike rows (spike + immediate reversal):")
cols = ['date', 'isin', 'close', 'pct_chg', 'next_pct_chg']
if 'name' in spike_rows.columns:
    cols = ['date', 'isin', 'name', 'close', 'pct_chg', 'next_pct_chg']
print(spike_rows[cols].to_string(index=False))

if len(spike_rows) == 0:
    print("No true spikes found.")
else:
    # Fix: replace spike close with prior day's close (prev_close)
    df['prev_close'] = df.groupby('isin')['close'].shift(1)
    df['next_close'] = df.groupby('isin')['close'].shift(-1)

    spike_idx = spike_rows.index

    # Use average of prev and next close as replacement
    replacement = ((df.loc[spike_idx, 'prev_close'] + df.loc[spike_idx, 'next_close']) / 2)
    scale_factor = replacement / df.loc[spike_idx, 'close']

    df.loc[spike_idx, 'close'] = replacement

    # Scale mc proportionally
    if 'mc' in df.columns:
        df.loc[spike_idx, 'mc'] = df.loc[spike_idx, 'mc'] * scale_factor

    df = df.drop(columns=['pct_chg', 'next_pct_chg', 'prev_close', 'next_close'])

    # Verify
    df2 = df.sort_values(['isin', 'date']).reset_index(drop=True)
    df2['pct_chg']      = df2.groupby('isin')['close'].pct_change()
    df2['next_pct_chg'] = df2.groupby('isin')['close'].pct_change().shift(-1)
    is_spike2 = (
        ((df2['pct_chg'] > THRESHOLD) & (df2['next_pct_chg'] < -THRESHOLD)) |
        ((df2['pct_chg'] < -THRESHOLD) & (df2['next_pct_chg'] > THRESHOLD))
    )
    remaining = df2[is_spike2]
    print(f"\nAfter fix: {len(remaining)} true spikes remaining.")
    df2 = df2.drop(columns=['pct_chg', 'next_pct_chg'])

    # Save
    df2.to_parquet(dst, index=False)
    print(f"\nCleaned data saved to: {dst}")

    # Sanity check on the known bad stock
    bad_isin = 'INE814H01029'
    check = df2[df2['isin'] == bad_isin][['date','close']].copy()
    check = check[(check['date'] >= '2018-11-28') & (check['date'] <= '2018-12-05')]
    print(f"\nSanity check for {bad_isin} around the spike date:")
    print(check.to_string(index=False))
    print("\nExpected: 30 Nov 2018 close should now be ~11 (avg of 11.09 and 11.55), not 85.75")
