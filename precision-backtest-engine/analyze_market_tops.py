"""
Analyze Shareholder Breadth as a predictor of Market Tops.
Dates to investigate: Feb 2018, Feb 2020, Nov 2024.
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

# 1. Calculate Aggregate Breadth over time
quarterly_dates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])

sh_df = dh.shareholding_df
breadth_history = []

for dt in quarterly_dates:
    universe = dh.get_universe(dt, size=1000)
    isins = universe['isin'].tolist()
    
    curr_q, prev_q = s._get_quarter_labels(dt, 4)
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = merged['curr'] < merged['prev']
    
    # Breadth = % of Top 1000 showing shareholder DECREASE (Cleaning)
    # Low Breadth = High Retail Crowding
    b_val = merged[merged['isin'].isin(isins)]['decreased'].mean()
    
    breadth_history.append({'date': dt, 'breadth': b_val})

df_breadth = pd.DataFrame(breadth_history).set_index('date')

# 2. Get Benchmark Prices
# Create a simple equal weighted index
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
    
    # Rebalance to top 1000
    universe = dh.get_universe(dt, size=1000)
    curr_holding = universe['isin'].tolist()
    bench_history.append({'date': dt, 'nav': nav})

df_bench = pd.DataFrame(bench_history).set_index('date')

# 3. Visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#0d1117')
ax2.set_facecolor('#0d1117')

# Top Panel: Benchmark Price
ax1.plot(df_bench.index, df_bench['nav'], color='#6bcb77', linewidth=2.5, label='Top 1000 EQ Index')
ax1.set_title("Market Peaks vs Shareholder Breadth (Top 1000)", color='white', fontsize=18, pad=20)
ax1.set_ylabel("Index Value", color='#aaaaaa')
ax1.grid(True, color='#222222', alpha=0.5)

# Bottom Panel: Breadth (% Shareholders DECREASING)
# High values = Good (Institutional accumulation / Retail cleanout)
# Low values = Warning (Retail piling in / Distribution)
ax2.plot(df_breadth.index, df_breadth['breadth'] * 100, color='#f4a261', linewidth=2, label='Breadth (% Decrease)')
ax2.axhline(60, color='#6bcb77', linestyle='--', alpha=0.3, label='Health Threshold (60%)')
ax2.axhline(40, color='#e71d36', linestyle='--', alpha=0.3, label='Danger Threshold (40%)')
ax2.set_ylabel("Breadth %", color='#aaaaaa')
ax2.grid(True, color='#222222', alpha=0.5)

# Highlight Specific Market Tops
tops = [
    (pd.Timestamp("2018-02-15"), "Feb 2018 Peak"),
    (pd.Timestamp("2020-02-15"), "Feb 2020 Peak"),
    (pd.Timestamp("2024-11-15"), "Nov 2024 Peak")
]

for t_date, label in tops:
    # Find closest quarterly date
    valid_dates = [d for d in df_breadth.index if d <= t_date]
    if not valid_dates: continue
    closest_date = max(valid_dates)
    
    # Mark on price
    price_val = df_bench.loc[closest_date, 'nav']
    ax1.annotate(label, xy=(closest_date, price_val), xytext=(20, 10),
                 textcoords='offset points', color='white',
                 arrowprops=dict(arrowstyle='->', color='#00d4ff'))
    ax1.axvline(closest_date, color='white', linestyle=':', alpha=0.3)
    
    # Mark on breadth
    breadth_val = df_breadth.loc[closest_date, 'breadth'] * 100
    ax2.annotate(f"{breadth_val:.1f}%", xy=(closest_date, breadth_val), xytext=(10, -15),
                 textcoords='offset points', color='#f4a261', fontsize=10)
    ax2.axvline(closest_date, color='white', linestyle=':', alpha=0.3)

ax1.legend(facecolor='#1a1a2e', labelcolor='white')
ax2.legend(facecolor='#1a1a2e', labelcolor='white')
ax1.tick_params(colors='white')
ax2.tick_params(colors='white')

# Analyze Divergences
# Check breadths at tops
results = []
for t_date, label in tops:
    valid_dates = [d for d in df_breadth.index if d <= t_date]
    if not valid_dates: continue
    dt = max(valid_dates)
    # Compare to 2 quarters prior
    idx = df_breadth.index.get_loc(dt)
    if idx >= 2:
        dt_prev = df_breadth.index[idx-2]
        b_curr = df_breadth.loc[dt, 'breadth']
        b_prev = df_breadth.loc[dt_prev, 'breadth']
        p_curr = df_bench.loc[dt, 'nav']
        p_prev = df_bench.loc[dt_prev, 'nav']
        results.append({
            'Event': label,
            'Date': dt.strftime('%Y-%m'),
            'Price_Chg': f"{(p_curr/p_prev-1)*100:+.1f}%",
            'Breadth_Chg': f"{(b_curr-b_prev)*100:+.1f}%",
            'Breadth_Level': f"{b_curr*100:.1f}%"
        })

print("\n--- Market Top Breadth Analysis ---")
print(pd.DataFrame(results).to_string(index=False))

out_path = repo_root / "market_top_breadth_analysis.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
