import pandas as pd
import re
from pathlib import Path

def apply_adjustments():
    print("--- Parsing Adjustment Factors from Log ---")
    log_path = Path('data/parallel_update.log')
    if not log_path.exists():
        print("Log file not found!")
        return

    adjustments = {}
    pattern = re.compile(r"ISIN ([A-Z0-9]+): New Price=([0-9.]+), Old Price=([0-9.]+)")
    
    with open(log_path, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                isin = match.group(1)
                new_p = float(match.group(2))
                old_p = float(match.group(3))
                if old_p != 0:
                    ratio = new_p / old_p
                    adjustments[isin] = ratio

    print(f"Found {len(adjustments)} stocks to adjust.")
    if not adjustments:
        return

    print("--- Loading price_data.parquet ---")
    db_path = Path('database/price_data.parquet')
    df = pd.read_parquet(db_path)
    df['date'] = pd.to_datetime(df['date'])
    
    cutoff_date = pd.Timestamp('2026-01-28')
    
    print("--- Applying Back-Adjustments ---")
    count = 0
    # Process updates in bulk if possible, or iterate
    # Iterating unique ISINs in adjustment list is safer
    
    # We can create a mapping series
    # But applying row-wise mask is slow.
    # Vectorized approach:
    # 1. Create a Series of Factors mapped to ISINs
    # 2. Join/Map this to the dataframe
    # 3. Apply multiplication where date < cutoff
    
    correction_map = pd.Series(adjustments, name='factor')
    
    # Join factor to df
    # Because not all ISINs need adjustment, we do left join or map
    # We want to preserve original index/order if possible, but map is easiest
    
    df['factor'] = df['isin'].map(correction_map).fillna(1.0)
    
    # Identify rows to modify: date < cutoff AND factor != 1.0
    mask = (df['date'] < cutoff_date) & (df['factor'] != 1.0)
    
    affected_rows = mask.sum()
    print(f"Applying adjustments to {affected_rows} historical rows...")
    
    cols_to_adjust = ['open', 'high', 'low', 'close']
    for col in cols_to_adjust:
        df.loc[mask, col] = df.loc[mask, col] * df.loc[mask, 'factor']
    
    # Drop factor col
    df.drop(columns=['factor'], inplace=True)
    
    print("--- Saving Updated Database ---")
    df.to_parquet(db_path, index=False)
    
    # Also update CSV
    print("--- Updating CSV ---")
    df.to_csv(db_path.with_suffix('.csv'), index=False)
    
    print("Done.")

if __name__ == "__main__":
    apply_adjustments()
