import pandas as pd
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def find_outliers():
    df = pd.read_csv(REPO_ROOT / 'database/shareholding_patterns.csv')

    # Sort to calculate QoQ
    q_order = ['Mar-2023', 'Jun-2023', 'Sep-2023', 'Dec-2023', 'Mar-2024', 'Jun-2024', 'Sep-2024', 'Dec-2024', 'Mar-2025', 'Jun-2025', 'Sep-2025', 'Dec-2025']
    df['q_cat'] = pd.Categorical(df['quarter'], categories=q_order, ordered=True)
    df = df.sort_values(['isin', 'q_cat']).dropna(subset=['q_cat'])

    outliers = set()
    for isin, group in df.groupby('isin'):
        group = group.sort_values('q_cat')
        group['fii_diff'] = group['fii_holding_pct'].diff()
        # If the jump is > 8% in a single quarter, it is likely a data bug from the fractional issue
        if (group['fii_diff'].abs() > 8).any():
            outliers.add(isin)

    print(f"Found {len(outliers)} total outlier ISINs with > 8% FII jumps.")
    
    # Save to JSON matching the expected format for our scraper
    out_file = REPO_ROOT / 'database/fii_outliers.json'
    with open(out_file, 'w') as f:
        json.dump({'stocks': [{'isin': i} for i in outliers]}, f, indent=2)
    print(f"Saved to {out_file.name}")

if __name__ == '__main__':
    find_outliers()
