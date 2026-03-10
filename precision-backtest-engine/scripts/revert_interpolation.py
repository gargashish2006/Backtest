import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
current_file = REPO_ROOT / 'database/shareholding_patterns.csv'
backup_file = REPO_ROOT / 'database/shareholding_patterns_backup_pre_tt.csv'

def revert():
    df_curr = pd.read_csv(current_file)
    df_back = pd.read_csv(backup_file)

    backup_keys = set(zip(df_back['isin'], df_back['quarter']))

    def get_true_sh(row):
        key = (row['isin'], row['quarter'])
        if key not in backup_keys:
            return np.nan # New row from TT, so no shareholder breadth exists natively
        return row['total_shareholders']

    df_curr['total_shareholders'] = df_curr.apply(get_true_sh, axis=1)

    nan_count = df_curr['total_shareholders'].isna().sum()
    print(f"Set {nan_count} artificial rows to NaN.")

    df_curr.to_csv(current_file, index=False)
    df_curr.to_parquet(current_file.with_suffix('.parquet'), index=False)

if __name__ == '__main__':
    revert()
