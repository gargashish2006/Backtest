import pandas as pd
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def backfill_outliers():
    outlier_file = REPO_ROOT / 'database/fii_outliers.json'
    with open(outlier_file) as f:
        outliers = [s['isin'] for s in json.load(f)['stocks']]
        
    sh_file = REPO_ROOT / 'database/shareholding_patterns.csv'
    df = pd.read_csv(sh_file)
    
    # Sort chronologically
    q_order = ['Mar-2023', 'Jun-2023', 'Sep-2023', 'Dec-2023', 'Mar-2024', 'Jun-2024', 'Sep-2024', 'Dec-2024', 'Mar-2025', 'Jun-2025', 'Sep-2025', 'Dec-2025']
    df['q_cat'] = pd.Categorical(df['quarter'], categories=q_order, ordered=True)
    
    outlier_mask = df['isin'].isin(outliers)
    df_outliers = df[outlier_mask].copy()
    
    updates = 0
    # For each outlier, use the Sep-2024 (or earliest Tickertape quarter) as the truth for all prior quarters
    for isin, group in df_outliers.groupby('isin'):
        tt_data = group[group['quarter'] == 'Sep-2024']
        if tt_data.empty:
            tt_data = group[group['quarter'] == 'Dec-2024'] # Fallback
            if tt_data.empty: continue
            
        truth_row = tt_data.iloc[0]
        promoter = truth_row['promoter_holding_pct']
        fii = truth_row['fii_holding_pct']
        dii = truth_row['dii_holding_pct']
        
        # All quarters strictly BEFORE Sep-2024
        prior_mask = (df['isin'] == isin) & (df['q_cat'] < 'Sep-2024')
        if prior_mask.any():
            df.loc[prior_mask, 'promoter_holding_pct'] = promoter
            df.loc[prior_mask, 'public_holding_pct'] = 100 - promoter
            df.loc[prior_mask, 'fii_holding_pct'] = fii
            df.loc[prior_mask, 'dii_holding_pct'] = dii
            updates += prior_mask.sum()
            
    # Drop temp column and save
    df = df.drop(columns=['q_cat'])
    df.to_csv(sh_file, index=False)
    df.to_parquet(sh_file.with_suffix('.parquet'), index=False)
    
    print(f"Backfilled {updates} prior quarters for {len(outliers)} outlier stocks.")

if __name__ == '__main__':
    backfill_outliers()
