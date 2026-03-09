import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sh_file = REPO_ROOT / 'database/shareholding_patterns.csv'

def repair_zero_shareholders():
    df = pd.read_csv(sh_file)
    
    # Identify zeros
    zero_mask = df['total_shareholders'] == 0
    initial_zeros = zero_mask.sum()
    print(f"Initial zeros to fix: {initial_zeros}")
    
    if initial_zeros == 0:
        return
        
    # We want to replace 0 with NaN so we can forward/backward fill per ISIN
    df.loc[zero_mask, 'total_shareholders'] = np.nan
    df.loc[df['total_outstanding_shares'] == 0.0, 'total_outstanding_shares'] = np.nan
    
    # Sort chronologically
    q_order = ['Mar-2023', 'Jun-2023', 'Sep-2023', 'Dec-2023', 'Mar-2024', 'Jun-2024', 'Sep-2024', 'Dec-2024', 'Mar-2025', 'Jun-2025', 'Sep-2025', 'Dec-2025']
    df['q_cat'] = pd.Categorical(df['quarter'], categories=q_order, ordered=True)
    df = df.sort_values(['isin', 'q_cat'])
    
    # Forward fill then backward fill within each ISIN group
    df['total_shareholders'] = df.groupby('isin')['total_shareholders'].ffill().bfill()
    df['total_outstanding_shares'] = df.groupby('isin')['total_outstanding_shares'].ffill().bfill()
    
    # Clean up
    df = df.drop(columns=['q_cat'])
    
    # Verify
    remaining_zeros = df['total_shareholders'].isna().sum()
    print(f"Remaining NaNs/Zeros: {remaining_zeros}")
    
    df.to_csv(sh_file, index=False)
    df.to_parquet(sh_file.with_suffix('.parquet'), index=False)
    print("Repaired total_shareholders and saved database.")

if __name__ == '__main__':
    repair_zero_shareholders()
