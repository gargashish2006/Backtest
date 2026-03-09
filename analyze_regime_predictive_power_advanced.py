"""
Deep Analytical Script: Industry-Segment Breadth Matrix & Lagged Correlations.
Identifies if breadth leads returns with specific lags and how industries differ across segments.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

s = MCPSStrategy(dh)
all_dates = dh.get_all_dates()

# Evaluation Dates (Every Quarter)
rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2026) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])

# Price Pivot
price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close')

# Data Storage
segment_history = []
industry_segment_history = []

for i, rd in enumerate(rdates):
    signal_date = rd - pd.Timedelta(days=7)
    actual_signal_date = max([d for d in all_dates if d <= signal_date])
    
    # Get Universe
    universe = dh.get_universe(actual_signal_date, size=1000)
    if universe.empty: continue
    
    seg_a_isins = universe.iloc[:200]['isin'].tolist()
    seg_b_isins = universe.iloc[200:]['isin'].tolist()
    
    # Breadth Data
    curr_q, prev_q = s._get_quarter_labels(actual_signal_date, 4)
    sh_df = dh.shareholding_df
    
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = (merged['curr'] < merged['prev']).astype(int)
    merged['group'] = merged['isin'].map(dh.isin_to_group)
    
    # Segment Breadth
    breadth_a = merged[merged['isin'].isin(seg_a_isins)]['decreased'].mean()
    breadth_b = merged[merged['isin'].isin(seg_b_isins)]['decreased'].mean()
    
    # Returns (1m, 3m, 6m)
    def get_fwd_ret(isins, months):
        price_at_start = price_pivot.loc[rd, isins] if rd in price_pivot.index else None
        target_date = rd + pd.DateOffset(months=months)
        actual_target_date = max([d for d in all_dates if d <= target_date])
        price_at_end = price_pivot.loc[actual_target_date, isins]
        if price_at_start is None or price_at_end is None: return 0
        return (price_at_end / price_at_start - 1).dropna().mean()

    res = {
        'Date': rd,
        'Breadth_A': breadth_a,
        'Breadth_B': breadth_b,
        'Ret_A_3m': get_fwd_ret(seg_a_isins, 3),
        'Ret_B_3m': get_fwd_ret(seg_b_isins, 3),
        'Ret_A_6m': get_fwd_ret(seg_a_isins, 6),
        'Ret_B_6m': get_fwd_ret(seg_b_isins, 6),
    }
    segment_history.append(res)
    
    # Industry-Level Breadth in Segments
    groups = merged['group'].dropna().unique()
    for g in groups:
        g_merged = merged[merged['group'] == g]
        b_a = g_merged[g_merged['isin'].isin(seg_a_isins)]['decreased'].mean()
        b_b = g_merged[g_merged['isin'].isin(seg_b_isins)]['decreased'].mean()
        if not np.isnan(b_a) or not np.isnan(b_b):
            industry_segment_history.append({
                'Date': rd,
                'Group': g,
                'Breadth_A': b_a,
                'Breadth_B': b_b,
                'Diff': b_b - b_a if (not np.isnan(b_b) and not np.isnan(b_a)) else np.nan
            })

df_seg = pd.DataFrame(segment_history)
df_ind = pd.DataFrame(industry_segment_history)

# 1. Lagged Correlation Analysis
lags = [0, 1, 2, 3] # Units of quarters
lag_results = []
for l in lags:
    shifted_ret = df_seg[['Ret_A_6m', 'Ret_B_6m']].shift(-l)
    corr = df_seg['Breadth_A'].corr(shifted_ret['Ret_A_6m'])
    corr_b = df_seg['Breadth_B'].corr(shifted_ret['Ret_B_6m'])
    lag_results.append({'Lag_Quarters': l, 'Corr_A': corr, 'Corr_B': corr_b})

df_lags = pd.DataFrame(lag_results)
print("\nLagged Correlation Table (Breadth(t) vs Forward 6m Return(t+l)):")
print(df_lags)

# 2. Industry-Segment Breadth Persistence
ind_summary = df_ind.groupby('Group')['Diff'].describe()
top_mid_bias = ind_summary.sort_values('mean', ascending=False).head(10)
top_large_bias = ind_summary.sort_values('mean', ascending=True).head(10)

print("\nGroups with strongest Mid-Cap Breadth Bias (Mid > Large):")
print(top_mid_bias['mean'])
print("\nGroups with strongest Large-Cap Breadth Bias (Large > Mid):")
print(top_large_bias['mean'])

# Plotting Lag Correlation
plt.figure(figsize=(10, 6))
plt.plot(df_lags['Lag_Quarters'], df_lags['Corr_A'], label='Large Cap (Top 200)', marker='o', color='#00d4ff')
plt.plot(df_lags['Lag_Quarters'], df_lags['Corr_B'], label='Mid Cap (201-1000)', marker='s', color='#6bcb77')
plt.title("Breadth Predictive Power at Different Lags", color='black')
plt.xlabel("Lag (Quarters)")
plt.ylabel("Correlation with Forward 6m Returns")
plt.grid(True, alpha=0.3)
plt.legend()
plt.savefig(repo_root / "breadth_lag_correlation.png")

# Heatmap Manual Implementation (Top Groups)
target_groups = top_mid_bias.index.tolist()[:5] + top_large_bias.index.tolist()[:5]
pivot_ind = df_ind[df_ind['Group'].isin(target_groups)].pivot(index='Date', columns='Group', values='Diff').fillna(0)

plt.figure(figsize=(14, 8))
im = plt.imshow(pivot_ind.T.values, cmap='RdYlGn', aspect='auto')
plt.colorbar(im, label='Breadth Diff (Mid - Large)')
plt.title("Industry Breadth Differential Heatmap")
plt.yticks(np.arange(len(target_groups)), target_groups)
plt.xlabel("Evaluation Quarters")
plt.savefig(repo_root / "industry_breadth_differential_heatmap.png")
print("\nSaved plots to repo root.")
