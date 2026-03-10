"""
Predictive Regime Analysis:
Correlates Segment-Specific Shareholder Breadth with Forward 6-Month Returns.
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

# Price Pivot for easy return calculation
price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close')

history = []

for i, rd in enumerate(rdates):
    # Forward 6m dates
    fwd_limit = i + 2 # Approx 6 months (2 quarters)
    if fwd_limit >= len(rdates): continue
    next_rd = rdates[fwd_limit]
    
    signal_date = rd - pd.Timedelta(days=7)
    actual_signal_date = max([d for d in all_dates if d <= signal_date])
    
    # Get Universe
    universe = dh.get_universe(actual_signal_date, size=1000)
    if universe.empty: continue
    
    seg_a_isins = universe.iloc[:200]['isin'].tolist()
    seg_b_isins = universe.iloc[200:]['isin'].tolist()
    
    # Calculate Breadth
    curr_q, prev_q = s._get_quarter_labels(actual_signal_date, 4)
    sh_df = dh.shareholding_df
    
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = (merged['curr'] < merged['prev']).astype(int)
    
    breadth_a = merged[merged['isin'].isin(seg_a_isins)]['decreased'].mean()
    breadth_b = merged[merged['isin'].isin(seg_b_isins)]['decreased'].mean()
    
    # Calculate Forward 6-Month Returns (Segment Wide)
    def calc_fwd_ret(isins):
        valid_isins = [isin for isin in isins if isin in price_pivot.columns]
        if not valid_isins: return 0
        prices_at_start = price_pivot.loc[rd, valid_isins]
        prices_at_end = price_pivot.loc[next_rd, valid_isins]
        rets = (prices_at_end / prices_at_start - 1).dropna()
        return rets.mean() if not rets.empty else 0

    ret_a = calc_fwd_ret(seg_a_isins)
    ret_b = calc_fwd_ret(seg_b_isins)
    
    history.append({
        'Date': rd,
        'Breadth_A': breadth_a,
        'Breadth_B': breadth_b,
        'FwdRet_A': ret_a,
        'FwdRet_B': ret_b,
        'Alpha_B_vs_A': ret_b - ret_a,
        'Breadth_Diff': breadth_b - breadth_a
    })

results = pd.DataFrame(history)

# Correlation Analysis
corr_matrix = results[['Breadth_A', 'Breadth_B', 'FwdRet_A', 'FwdRet_B', 'Alpha_B_vs_A', 'Breadth_Diff']].corr()
print("\nCorrelation Matrix (Breadth vs Forward Returns):")
print(corr_matrix)

# Specific Correlation: Does Breadth_Diff predict Alpha_B_vs_A?
final_corr = results['Breadth_Diff'].corr(results['Alpha_B_vs_A'])
print(f"\nCorrelation between (Breadth B - Breadth A) and (Forward Return B - Forward Return A): {final_corr:.4f}")

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
fig.patch.set_facecolor('#0d1117')

def style_ax(ax, title):
    ax.set_facecolor('#0d1117')
    ax.set_title(title, color='white', pad=15)
    ax.tick_params(colors='white')
    ax.grid(True, color='#222222')
    ax.legend(facecolor='#1a1a2e', labelcolor='white')

style_ax(ax1, "Shareholder Breadth Differential (Mid - Large)")
ax1.plot(results['Date'], results['Breadth_Diff'], color='#f4a261', linewidth=2, label='Breadth B - Breadth A')
ax1.axhline(0, color='white', linestyle='--', alpha=0.3)

style_ax(ax2, "Forward 6-Month Alpha (Mid - Large)")
ax2.plot(results['Date'], results['Alpha_B_vs_A'], color='#e76f51', linewidth=2, label='Fwd 6M Alpha (B - A)')
ax2.axhline(0, color='white', linestyle='--', alpha=0.3)

out_path = repo_root / "breadth_return_correlation.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
