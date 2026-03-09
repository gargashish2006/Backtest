"""
Diagnostic Script: Why HDFC Bank was excluded in Feb 2026?
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

# Strategy Instance
s = MCPSStrategy(dh, universe_size=500)
rebalance_date = pd.Timestamp("2026-02-15")
signal_date = rebalance_date - pd.Timedelta(days=7) # T-7 logic in strategy
all_dates = dh.get_all_dates()
actual_signal_date = max([d for d in all_dates if d <= signal_date])

print(f"Diagnostics for actual_signal_date: {actual_signal_date}")

# Target ISIN - Search for HDFC Bank
hdfc_isins = [k for k, v in dh.isin_to_name.items() if "HDFC Bank" in v]
if not hdfc_isins:
    print("Could not find HDFC Bank ISIN!")
    exit()
isin = hdfc_isins[0]
print(f"Company: {dh.isin_to_name.get(isin, 'Unknown')} ({isin})")
print(f"Industry: {dh.isin_to_industry.get(isin, 'Unknown')}")
print(f"Group: {dh.isin_to_group.get(isin, 'Unknown')}")

# 1. Universe Check
universe = dh.get_universe(actual_signal_date, size=500)
in_universe = isin in universe['isin'].values
print(f"1. In Top 500 Universe: {in_universe}")

# 2. Industry Group Filter Check
sh_df = dh.shareholding_df
curr_q, prev_q = s._get_quarter_labels(actual_signal_date, 4)
print(f"Quarters for Group Filter: {curr_q} vs {prev_q}")

def get_sh_stats(q):
    return sh_df[sh_df['quarter'] == q][['isin', 'total_shareholders']]

curr_sh_df = get_sh_stats(curr_q)
prev_sh_df = get_sh_stats(prev_q)
merged_sh = pd.merge(curr_sh_df, prev_sh_df, on='isin', suffixes=('_curr', '_prev'))
merged_sh['decreased'] = merged_sh['total_shareholders_curr'] < merged_sh['total_shareholders_prev']
merged_sh['group'] = merged_sh['isin'].map(dh.isin_to_group)
group_stats = merged_sh.dropna(subset=['group']).groupby('group')['decreased'].mean().reset_index()
n_top = max(1, int(len(group_stats) * 0.50))
top_groups = group_stats.sort_values('decreased', ascending=False).head(n_top)['group'].tolist()

my_group = dh.isin_to_group.get(isin)
group_breadth = group_stats[group_stats['group'] == my_group]['decreased'].values[0] if my_group in group_stats['group'].values else 0
in_top_group = my_group in top_groups
print(f"2. Group Filter ({my_group}):")
print(f"   - Group Breadth (% decreasing shareholders): {group_breadth*100:.1f}%")
print(f"   - In Top 50% Groups: {in_top_group}")

# 3. MCPS Change Check
mc_now = s._get_mc_on_date(actual_signal_date).get(isin, 0)
mc_prev_date = actual_signal_date - pd.DateOffset(months=12)
mc_prev = s._get_mc_on_date(mc_prev_date).get(isin, 0)

sh_now = curr_sh_df[curr_sh_df['isin'] == isin]['total_shareholders'].values[0] if isin in curr_sh_df['isin'].values else 0
sh_prev = prev_sh_df[prev_sh_df['isin'] == isin]['total_shareholders'].values[0] if isin in prev_sh_df['isin'].values else 0

if sh_now > 0 and sh_prev > 0 and mc_now > 0 and mc_prev > 0:
    mcps_now = mc_now / sh_now
    mcps_prev = mc_prev / sh_prev
    mcps_positive = mcps_now > mcps_prev
    print(f"3. MCPS Calculation:")
    print(f"   - M-Cap Now: {mc_now/1e9:.2f}B | Prev: {mc_prev/1e9:.2f}B")
    print(f"   - SH Now: {sh_now:,} | Prev: {sh_prev:,}")
    print(f"   - MCPS Now: {mcps_now:.2f} | Prev: {mcps_prev:.2f}")
    print(f"   - MCPS Positive: {mcps_positive}")
else:
    print(f"3. MCPS Calculation: Data Missing")

# 4. Filter Check (Liquidity and RSI)
# Liquidity
liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
liq_df = dh.price_df[(dh.price_df['date'].isin(liquidity_window)) & (dh.price_df['isin'] == isin)]
med_val = liq_df['traded_val'].median() if not liq_df.empty else 0
liq_threshold = mc_now * 0.00005 
liq_pass = med_val > liq_threshold
print(f"4. Filters:")
print(f"   - Median 21d Vol: {med_val/1e6:.2f}M | Threshold: {liq_threshold/1e6:.2f}M")
print(f"   - Liquidity Pass: {liq_pass}")

# RSI
from strategies.cs15_strategy import CS15Strategy
temp_s = CS15Strategy(dh) # Use CS15 for easier RSI precompute if needed, or just manual
# Strategy.precompute_rsi builds a cache indexed by elements of the dates list
s.precompute_rsi([rebalance_date])
try:
    rsi_val = s.rsi_cache.loc[rebalance_date, isin]
except KeyError:
    rsi_val = 0
rsi_pass = rsi_val > 40
print(f"   - RSI (Weekly): {rsi_val:.2f} | Threshold: 40")
print(f"   - RSI Pass: {rsi_pass}")
