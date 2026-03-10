#!/usr/bin/env python3
"""Print industry lists for hierarchical strategy for Dec-2025 and Dec-2024 sorted by trend."""
import pandas as pd
from pathlib import Path
import sys
# ensure repo root is on path for imports
repo_root = Path(__file__).resolve().parents[1]
sys.path.append(str(repo_root))
from strategies.industry_4q_hierarchical_pct_top1000_final_10ind_3stocks import Industry4QHierarchicalPctTop1000FinalStrategy

out_dir = Path(__file__).parent / 'outputs'
out_dir.mkdir(exist_ok=True)

# fallback: if parquet engine (pyarrow) is missing, read CSV equivalent
orig_read_parquet = pd.read_parquet
def _read_parquet_fallback(path, *args, **kwargs):
    try:
        return orig_read_parquet(path, *args, **kwargs)
    except Exception:
        p = Path(path)
        csv_path = p.with_suffix('.csv')
        # price data needs date parsing; other tables may not have 'date'
        if 'price' in p.name:
            return pd.read_csv(csv_path, parse_dates=['date'])
        return pd.read_csv(csv_path)

pd.read_parquet = _read_parquet_fallback

strategy = Industry4QHierarchicalPctTop1000FinalStrategy()

dates = [('Dec-2025', pd.Timestamp('2025-12-31')), ('Dec-2024', pd.Timestamp('2024-12-31'))]
all_tables = {}
for label, date in dates:
    hier = strategy.calculate_hierarchical_contrarian_percentiles(date)
    trend = strategy.calculate_industry_trend_metrics(date)
    if hier.empty or trend.empty:
        print(f"No data for {label} ({date.date()})")
        continue
    merged = hier.merge(trend[['industry','pct_above_ma','total_stocks']], on='industry', how='left')
    # ensure total_stocks column exists (may come from either side of merge)
    if 'total_stocks' not in merged.columns:
        if 'total_stocks_x' in merged.columns:
            merged['total_stocks'] = merged['total_stocks_x']
        elif 'total_stocks_y' in merged.columns:
            merged['total_stocks'] = merged['total_stocks_y']
        else:
            merged['total_stocks'] = merged['industry'].map(hier.set_index('industry')['total_stocks'])
    prices = strategy.price_df[strategy.price_df['date'] <= date]
    latest = prices.sort_values('date').groupby('isin').last().reset_index()
    latest = latest.merge(strategy.industry_df[['isin','industry']], on='isin', how='left')
    median_price = latest.groupby('industry')['close'].median().reset_index().rename(columns={'close':'median_price'})
    merged = merged.merge(median_price, on='industry', how='left')
    merged = merged.sort_values('pct_above_ma', ascending=False)
    display_cols = ['industry','pct_decreasing','industry_pct','group_pct','hierarchical_pct','pct_above_ma','total_stocks','median_price']
    table = merged[display_cols].reset_index(drop=True)
    all_tables[label] = table
    # save
    table.to_csv(out_dir/f'industry_list_{label.replace("-","_")}.csv', index=False)
    print('\n====', label, date.date(), '====')
    print(table.to_string(index=False))

# Optionally save combined file
combined_path = out_dir / 'industry_lists_dec2024_dec2025.csv'
with combined_path.open('w') as f:
    for label, table in all_tables.items():
        f.write(f'## {label}\n')
        table.to_csv(f, index=False)
        f.write('\n')
print('\nSaved individual CSVs and combined file to', out_dir)
