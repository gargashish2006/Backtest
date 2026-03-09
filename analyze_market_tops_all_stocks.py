"""
Analyze All-Stock Shareholder Breadth as a predictor of Market Tops.
Compare it with Top 1000 Breadth.
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
all_dates = sorted(dh.get_all_dates())
sh_df = dh.shareholding_df

# Quarterly rebalance dates
quarterly_dates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])

breadth_history = []

for dt in quarterly_dates:
    # 1. Top 1000 Universe
    universe_1000 = dh.get_universe(dt, size=1000)
    isins_1000 = universe_1000['isin'].tolist()
    
    # 2. All Stocks Universe (for that date)
    isins_all = dh.price_df[dh.price_df['date'] == dt]['isin'].tolist()
    
    curr_q, prev_q = s._get_quarter_labels(dt, 4)
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = merged['curr'] < merged['prev']
    
    b_1000 = merged[merged['isin'].isin(isins_1000)]['decreased'].mean()
    b_all = merged[merged['isin'].isin(isins_all)]['decreased'].mean()
    
    breadth_history.append({
        'date': dt, 
        'breadth_1000': b_1000, 
        'breadth_all': b_all,
        'count_all': len(isins_all)
    })

df_breadth = pd.DataFrame(breadth_history).set_index('date')

# Comparison Table
tops = [
    (pd.Timestamp("2018-02-15"), "Feb 2018 Peak"),
    (pd.Timestamp("2020-02-15"), "Feb 2020 Peak"),
    (pd.Timestamp("2024-11-15"), "Nov 2024 Peak")
]

results = []
for t_date, label in tops:
    valid_dates = [d for d in df_breadth.index if d <= t_date]
    if not valid_dates: continue
    dt = max(valid_dates)
    results.append({
        'Peak': label,
        'Top 1000 Breadth': f"{df_breadth.loc[dt, 'breadth_1000']*100:.1f}%",
        'All-Stock Breadth': f"{df_breadth.loc[dt, 'breadth_all']*100:.1f}%",
        'Total Stocks': int(df_breadth.loc[dt, 'count_all'])
    })

print("\n--- Breadth Comparison: Top 1000 vs All Stocks ---")
print(pd.DataFrame(results).to_string(index=False))

# Visualization
fig, ax = plt.subplots(figsize=(15, 8))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(df_breadth.index, df_breadth['breadth_1000'] * 100, color='#00d4ff', linewidth=2.5, label='Top 1000 Breadth')
ax.plot(df_breadth.index, df_breadth['breadth_all'] * 100, color='#ff9500', linewidth=2.0, linestyle='--', label='All-Stock Breadth')

ax.axhline(40, color='#e71d36', linestyle=':', alpha=0.5, label='Danger Zone (40%)')

# Highlight peaks
for t_date, label in tops:
    ax.axvline(t_date, color='white', linestyle=':', alpha=0.3)
    ax.text(t_date, 90, label, color='white', rotation=90, va='top', ha='right', fontsize=9)

ax.set_title("Breadth Sensitivity: Top 1000 vs. All-Stock Portfolio", color='white', fontsize=18)
ax.set_ylabel("Breadth % (Stocks Decreasing Shareholders)", color='#aaaaaa')
ax.legend(facecolor='#1a1a2e', labelcolor='white')
ax.grid(True, color='#222222', alpha=0.5)
ax.tick_params(colors='white')

out_path = repo_root / "all_stock_breadth_comparison.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
