"""
Combined Plot: Top 1000 Benchmark NAV (Frictionless) with Shareholder Breadth Overlay.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

s = MCPSStrategy(dh)
all_dates = sorted(dh.get_all_dates())
sh_df = dh.shareholding_df

# Quarterly rebalance dates
quarterly_dates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
quarterly_dates = [d for d in quarterly_dates if pd.Timestamp("2017-05-15") <= d <= pd.Timestamp("2026-02-05")]

# 1. Calculate Breadth (Top 1000)
breadth_history = []
for dt in quarterly_dates:
    universe = dh.get_universe(dt, size=1000)
    isins = universe['isin'].tolist()
    curr_q, prev_q = s._get_quarter_labels(dt, 4)
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = merged['curr'] < merged['prev']
    b_val = merged[merged['isin'].isin(isins)]['decreased'].mean()
    breadth_history.append({'date': dt, 'breadth': b_val})
df_breadth = pd.DataFrame(breadth_history).set_index('date')

# 2. Calculate Benchmark NAV (Quarterly Rebalanced Top 1000)
price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close').ffill()
bench_history = []
nav = 100.0
curr_holding = []

for i, dt in enumerate(quarterly_dates):
    if i > 0:
        prev_dt = quarterly_dates[i-1]
        valid = [isin for isin in curr_holding if isin in price_pivot.columns]
        ret = (price_pivot.loc[dt, valid] / price_pivot.loc[prev_dt, valid]).mean()
        nav *= ret
    universe = dh.get_universe(dt, size=1000)
    curr_holding = universe['isin'].tolist()
    bench_history.append({'date': dt, 'nav': nav})
df_bench = pd.DataFrame(bench_history).set_index('date')

# 3. Visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [2.5, 1]})
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#0d1117')
ax2.set_facecolor('#0d1117')

# Top Plot: Benchmark with Danger Shading
ax1.plot(df_bench.index, df_bench['nav'], color='#6bcb77', linewidth=3, label='Top 1000 Benchmark (Frictionless)')

# Shading for Breadth < 40% (Danger Zone)
for i in range(len(df_breadth)-1):
    d1 = df_breadth.index[i]
    d2 = df_breadth.index[i+1]
    b = df_breadth.iloc[i]['breadth']
    if b < 0.40:
        ax1.axvspan(d1, d2, color='#e71d36', alpha=0.15)
        ax2.axvspan(d1, d2, color='#e71d36', alpha=0.1)

# Annotate peaks
tops = [(pd.Timestamp("2018-02-15"), "Feb 2018"), (pd.Timestamp("2020-02-15"), "Feb 2020"), (pd.Timestamp("2024-11-15"), "Nov 2024")]
for t_date, label in tops:
    valid_dates = [d for d in df_bench.index if d <= t_date]
    if valid_dates:
        closest = max(valid_dates)
        ax1.scatter(closest, df_bench.loc[closest, 'nav'], color='white', s=100, zorder=5)
        ax1.annotate(label, (closest, df_bench.loc[closest, 'nav']), xytext=(0, 15),
                     textcoords='offset points', color='white', ha='center', fontweight='bold')

ax1.set_title("Top 1000 Performance vs Shareholder Breadth Sentiment", color='white', fontsize=20, pad=20)
ax1.set_ylabel("Indexed Price (Base 100)", color='#aaaaaa')
ax1.grid(True, color='#222222', alpha=0.5)
ax1.legend(facecolor='#1a1a2e', labelcolor='white', loc='upper left')

# Bottom Plot: Breadth Area Chart
ax2.fill_between(df_breadth.index, df_breadth['breadth']*100, color='#00d4ff', alpha=0.2)
ax2.plot(df_breadth.index, df_breadth['breadth']*100, color='#00d4ff', linewidth=2, label='Shareholder Breadth %')
ax2.axhline(40, color='#e71d36', linestyle='--', alpha=0.5, label='Danger Threshold (40%)')

ax2.set_ylabel("Breadth %", color='#aaaaaa')
ax2.set_ylim(0, 100)
ax2.grid(True, color='#222222', alpha=0.5)
ax2.legend(facecolor='#1a1a2e', labelcolor='white')

ax1.tick_params(colors='white')
ax2.tick_params(colors='white')
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

out_path = repo_root / "bench_breadth_overlay.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"Saved overlay plot to: {out_path}")
plt.show()
