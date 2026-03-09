"""
Diagnostic Script: Industry Ranking for Feb 2026
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

s = MCPSStrategy(dh, universe_size=500)
rebalance_date = pd.Timestamp("2026-02-15")
signal_date = rebalance_date - pd.Timedelta(days=7)
all_dates = dh.get_all_dates()
actual_signal_date = max([d for d in all_dates if d <= signal_date])

# 1. Group Filter
curr_q, prev_q = s._get_quarter_labels(actual_signal_date, 4)
sh_df = dh.shareholding_df
curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr_sh'})
prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev_sh'})
merged = pd.merge(curr_sh, prev_sh, on='isin')
merged['decreased'] = merged['curr_sh'] < merged['prev_sh']
merged['group'] = merged['isin'].map(dh.isin_to_group)
group_stats = merged.dropna(subset=['group']).groupby('group')['decreased'].mean().reset_index()
n_top = max(1, int(len(group_stats) * 0.50))
top_groups = group_stats.sort_values('decreased', ascending=False).head(n_top)['group'].tolist()
merged = merged[merged['group'].isin(top_groups)]

# 2. MCPS Ranking
mc_now = s._get_mc_on_date(actual_signal_date)
mc_prev = s._get_mc_on_date(actual_signal_date - pd.DateOffset(years=1))
merged['mc_now'] = merged['isin'].map(mc_now)
merged['mc_prev'] = merged['isin'].map(mc_prev)
merged = merged.dropna(subset=['mc_now', 'mc_prev'])
merged['mcps_now'] = merged['mc_now'] / merged['curr_sh']
merged['mcps_prev'] = merged['mc_prev'] / merged['prev_sh']
merged['mcps_positive'] = merged['mcps_now'] > merged['mcps_prev']
merged['industry'] = merged['isin'].map(dh.isin_to_industry)

ind_ranked = (merged.groupby('industry')
              .agg(mcps_positive_pct=('mcps_positive', 'mean'), count=('isin', 'count'))
              .reset_index())
ind_ranked = ind_ranked.sort_values(['mcps_positive_pct', 'count'], ascending=False)

print("\nTop Industries by MCPS Signal Breadth:")
print(ind_ranked.head(20).to_string(index=False))

my_ind = "Private Sector Bank"
if my_ind in ind_ranked['industry'].values:
    print(f"\nStats for {my_ind}:")
    print(ind_ranked[ind_ranked['industry'] == my_ind].to_string(index=False))
else:
    print(f"\n{my_ind} not in ranked list (maybe group excluded?)")
    # Check if Banks was in top groups
    banks_in = "Banks" in top_groups
    print(f"Was 'Banks' group in Top 50% Groups? {banks_in}")
    if not banks_in:
        print(f"Banks group breadth: {group_stats[group_stats['group']=='Banks']['decreased'].values[0]*100:.1f}%")
        print(f"Threshold group breadth: {group_stats.sort_values('decreased', ascending=False).iloc[n_top-1]['decreased']*100:.1f}%")
