"""
Analyze Market-Wide Investor Density: (Total Market Cap / Total Shareholders).
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from data.data_handler import DataHandler

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

all_dates = sorted(dh.get_all_dates())
sh_df = dh.shareholding_df

# Quarterly rebalance dates
quarterly_dates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
quarterly_dates = [d for d in quarterly_dates if pd.Timestamp("2017-05-15") <= d <= pd.Timestamp("2026-02-05")]

density_history = []

for dt in quarterly_dates:
    # 1. Get market cap for all stocks on this date
    # Note: price_df has 'mc' column
    prices = dh.price_df[dh.price_df['date'] == dt][['isin', 'mc']]
    
    year = dt.year
    month = dt.month
    # Mapping rebalance month to reporting quarter
    # Feb rebalance -> Dec (prev year)
    # May rebalance -> Mar (curr year)
    # Aug rebalance -> Jun (curr year)
    # Nov rebalance -> Sep (curr year)
    if month == 2: q = f"Dec-{year-1}"
    elif month == 5: q = f"Mar-{year}"
    elif month == 8: q = f"Jun-{year}"
    else: q = f"Sep-{year}"
    
    sh_quarter = sh_df[sh_df['quarter'] == q][['isin', 'total_shareholders']]
    
    if sh_quarter.empty:
        # Try fallback to previous year label logic if current fails
        # (The FY labeling can be tricky depending on how the data was ingested)
        continue
        
    merged = pd.merge(prices, sh_quarter, on='isin').dropna()
    
    if not merged.empty:
        total_mc = merged['mc'].sum()
        total_sh = merged['total_shareholders'].sum()
        density = total_mc / total_sh
        
        density_history.append({
            'date': dt,
            'total_mc': total_mc,
            'total_sh': total_sh,
            'density': density,
            'stock_count': len(merged)
        })

df_density = pd.DataFrame(density_history).set_index('date')

# Benchmark for comparison
price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close').ffill()
bench_history = []
nav = 100.0
curr_holding = []
for i, dt in enumerate(quarterly_dates):
    if i > 0:
        prev_dt = quarterly_dates[i-1]
        valid = [isin for isin in curr_holding if isin in price_pivot.columns]
        if valid:
            ret = (price_pivot.loc[dt, valid] / price_pivot.loc[prev_dt, valid]).mean()
            nav *= ret
    universe = dh.get_universe(dt, size=1000)
    curr_holding = universe['isin'].tolist()
    bench_history.append({'date': dt, 'nav': nav})
df_bench = pd.DataFrame(bench_history).set_index('date')

# Visualisation
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#0d1117')
ax2.set_facecolor('#0d1117')

# Top: Benchmark Price
ax1.plot(df_bench.index, df_bench['nav'], color='#6bcb77', linewidth=2.5, label='Top 1000 Benchmark')
ax1.set_title("Market Valuation vs. Investor Density (Market-Wide)", color='white', fontsize=18, pad=20)
ax1.set_ylabel("Price Index", color='#aaaaaa')
ax1.grid(True, color='#222222', alpha=0.5)

# Bottom: Investor Density (MC / Shareholders)
# Units: Usually millions or billions per shareholder
ax2.plot(df_density.index, df_density['density'], color='#00d4ff', linewidth=3, label='Investor Density (MC / Total SH)')
ax2.set_ylabel("Avg Market Cap per Investor", color='#aaaaaa')
ax2.grid(True, color='#222222', alpha=0.5)

# Secondary axis for total shareholder growth (optional context)
ax3 = ax2.twinx()
ax3.plot(df_density.index, df_density['total_sh'] / 1e6, color='#ff9500', alpha=0.3, label='Total Shareholders (Millions)')
ax3.set_ylabel("Total Shareholders (M)", color='#ff9500', alpha=0.5)
ax3.tick_params(axis='y', colors='#ff9500')

# Annotate peaks
tops = [(pd.Timestamp("2018-02-15"), "Feb 2018"), (pd.Timestamp("2020-02-15"), "Feb 2020"), (pd.Timestamp("2024-11-15"), "Nov 2024")]
for t_date, label in tops:
    ax1.axvline(t_date, color='white', linestyle=':', alpha=0.3)
    ax2.axvline(t_date, color='white', linestyle=':', alpha=0.3)

ax1.legend(facecolor='#1a1a2e', labelcolor='white')
ax2.legend(facecolor='#1a1a2e', labelcolor='white', loc='upper left')
ax1.tick_params(colors='white')
ax2.tick_params(colors='white')

out_path = repo_root / "market_investor_density.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"Saved density plot to: {out_path}")

print("\n--- Investor Density Detail ---")
print(df_density[['total_sh', 'density', 'stock_count']].tail(5))
plt.show()
