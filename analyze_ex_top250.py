"""
Analyze Breadth and Investor Density EXCLUDING the Top 250 stocks (Small/Nano-Cap Focus).
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

all_dates = sorted(dh.get_all_dates())
sh_df = dh.shareholding_df

# Quarterly dates
quarterly_dates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
quarterly_dates = [d for d in quarterly_dates if pd.Timestamp("2017-05-15") <= d <= pd.Timestamp("2026-02-05")]

history = []

for dt in quarterly_dates:
    year, month = dt.year, dt.month
    
    # 1. Selection: All stocks vs. Top 250
    all_day_data = dh.price_df[dh.price_df['date'] == dt][['isin', 'mc']]
    top_250 = all_day_data.sort_values('mc', ascending=False).head(250)['isin'].tolist()
    ex_250_data = all_day_data[~all_day_data['isin'].isin(top_250)]
    
    # 2. Quarter labels
    if month == 2: q, q_prev = f"Dec-{year-1}", f"Dec-{year-2}"
    elif month == 5: q, q_prev = f"Mar-{year}", f"Mar-{year-1}"
    elif month == 8: q, q_prev = f"Jun-{year}", f"Jun-{year-1}"
    else: q, q_prev = f"Sep-{year}", f"Sep-{year-1}"
    
    curr_sh = sh_df[sh_df['quarter'] == q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == q_prev][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    
    if curr_sh.empty or prev_sh.empty: continue
        
    sh_merged = pd.merge(curr_sh, prev_sh, on='isin')
    sh_merged['decreased'] = sh_merged['curr'] < sh_merged['prev']
    
    # 3. Density & Breadth for Ex-Top 250
    density_merged = pd.merge(ex_250_data, curr_sh, on='isin').dropna()
    if not density_merged.empty:
        total_mc = density_merged['mc'].sum()
        total_sh = density_merged['curr'].sum()
        density = total_mc / total_sh
        
        breadth_merged = pd.merge(ex_250_data, sh_merged, on='isin')
        breadth = breadth_merged['decreased'].mean()
        
        history.append({
            'date': dt,
            'breadth_ex250': breadth,
            'density_ex250': density,
            'stock_count': len(ex_250_data)
        })

df_results = pd.DataFrame(history).set_index('date')

# Benchmark (Top 1000)
nav_history = []
nav = 100.0
curr_holding = []
price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close').ffill()
for i, dt in enumerate(quarterly_dates):
    if i > 0:
        prev_dt = quarterly_dates[i-1]
        valid = [isin for isin in curr_holding if isin in price_pivot.columns]
        if valid: nav *= (price_pivot.loc[dt, valid] / price_pivot.loc[prev_dt, valid]).mean()
    universe = dh.get_universe(dt, size=1000)
    curr_holding = universe['isin'].tolist()
    nav_history.append({'date': dt, 'nav': nav})
df_bench = pd.DataFrame(nav_history).set_index('date')

# Plotting
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 18), sharex=True)
fig.patch.set_facecolor('#0d1117')
for ax in [ax1, ax2, ax3]: ax.set_facecolor('#0d1117')

ax1.plot(df_bench.index, df_bench['nav'], color='#6bcb77', linewidth=2.5, label='Top 1000 Index')
ax1.set_title("Ex-Top 250 Segment Analysis (Small/Nano Focus)", color='white', fontsize=18)
ax1.set_ylabel("Price Index", color='#aaaaaa')
ax1.grid(True, color='#222222', alpha=0.5)

ax2.plot(df_results.index, df_results['breadth_ex250']*100, color='#ff2e63', linewidth=3, label='Ex-Top 250 Breadth %')
ax2.axhline(40, color='white', linestyle='--', alpha=0.3, label='Danger (40%)')
ax2.set_ylabel("Breadth % (Rank 251+)", color='#aaaaaa')
ax2.set_ylim(0, 100)
ax2.grid(True, color='#222222', alpha=0.5)

# Density vs Total SH count contextual shade
ax3.plot(df_results.index, df_results['density_ex250'], color='#08d9d6', linewidth=3, label='Ex-Top 250 Investor Density')
ax3.set_ylabel("Avg MC per Investor (Ex-250)", color='#aaaaaa')
ax3.grid(True, color='#222222', alpha=0.5)

tops = [(pd.Timestamp("2018-02-15"), "Feb 2018"), (pd.Timestamp("2020-02-15"), "Feb 2020"), (pd.Timestamp("2024-11-15"), "Nov 2024")]
for t_date, label in tops:
    for ax in [ax1, ax2, ax3]: ax.axvline(t_date, color='white', linestyle=':', alpha=0.3)

for ax in [ax1, ax2, ax3]:
    ax.legend(facecolor='#1a1a2e', labelcolor='white')
    ax.tick_params(colors='white')

out_path = repo_root / "ex_top250_analysis.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"Saved segment analysis plot to: {out_path}")
plt.show()
