"""
Find the stock causing the price spike in the MCPS15 NAV between 2018-2019.
The Nov 2018 portfolio was:
['INE884B01025', 'INE752E01010', 'INE120A01034', 'INE536A01023', 'INE640A01023',
 'INE037A01022', 'INE116A01032', 'INE245A01021', 'INE814H01029', 'INE036A01016',
 'INE467B01029', 'INE009A01021', 'INE860A01027', 'INE371A01025', 'INE545A01024']

Look for any stock with a single-day price spike > 30% followed by a reversal.
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data.parquet")
dh.load_data()

# Nov 2018 portfolio holdings
portfolio_isins = [
    'INE884B01025', 'INE752E01010', 'INE120A01034', 'INE536A01023', 'INE640A01023',
    'INE037A01022', 'INE116A01032', 'INE245A01021', 'INE814H01029', 'INE036A01016',
    'INE467B01029', 'INE009A01021', 'INE860A01027', 'INE371A01025', 'INE545A01024'
]

# Focus window: Nov 2018 to Feb 2019
window = dh.price_df[
    (dh.price_df['isin'].isin(portfolio_isins)) &
    (dh.price_df['date'] >= '2018-11-01') &
    (dh.price_df['date'] <= '2019-02-28')
].copy()

# Compute daily % change per stock
window = window.sort_values(['isin', 'date'])
window['pct_chg'] = window.groupby('isin')['close'].pct_change() * 100

# Find any single-day moves > 25%
big_moves = window[window['pct_chg'].abs() > 25].sort_values('pct_chg', ascending=False)
print("=== Single-day moves > 25% in portfolio (Nov 2018 - Feb 2019) ===")
if big_moves.empty:
    print("None found — widening search to > 15%...")
    big_moves = window[window['pct_chg'].abs() > 15].sort_values('pct_chg', ascending=False)

cols = ['date', 'isin', 'close', 'pct_chg']
if 'name' in big_moves.columns:
    cols = ['date', 'isin', 'name', 'close', 'pct_chg']
print(big_moves[cols].to_string(index=False))

# Also print the full price series for any stock with a big move
spike_isins = big_moves['isin'].unique()
for isin in spike_isins:
    stock_data = window[window['isin'] == isin][['date', 'close', 'pct_chg']]
    name = big_moves[big_moves['isin'] == isin]['name'].iloc[0] if 'name' in big_moves.columns else isin
    print(f"\n── Full price series for {isin} ({name}) ──")
    print(stock_data.to_string(index=False))
