import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
df = pd.read_csv(REPO_ROOT / 'database/shareholding_patterns.csv')

zero_sh = df[df['total_shareholders'] == 0]
print(f"Rows with zero total_shareholders: {len(zero_sh)}")
print(zero_sh[['isin', 'quarter', 'data_source', 'total_shareholders']].head(10))

