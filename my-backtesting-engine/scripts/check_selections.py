import sys
from pathlib import Path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import pandas as pd
from strategies.industry_group.contrarian_sync15_top1000 import ContrarianSync15Top1000

strat = ContrarianSync15Top1000()
info = pd.read_parquet('database/industry_info.parquet')

for d in ['2020-02-15', '2020-05-15']:
    date = pd.Timestamp(d)
    isins = strat.calculate_selection(date)
    result = info[info['isin'].isin(isins)][['company_name', 'industry']]
    print(f"\nREBALANCE DATE: {d}")
    print(result.to_string(index=False))
