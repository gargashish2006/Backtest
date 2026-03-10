"""
Multi-Segment Breadth Analysis vs Top 1000 Benchmark.
Plots:
1. Top 1000 Benchmark NAV (Left Y)
2. Shareholder Breadth % Top 200 (Right Y)
3. Shareholder Breadth % 201-1000 (Right Y)
4. Shareholder Breadth % All Stocks (Right Y)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import warnings
from data.data_handler import DataHandler

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = sorted(dh.get_all_dates())

# ── 1. Calculate Top 1000 Benchmark NAV ───────────────────────────────────────
print("Calculating Top 1000 Benchmark NAV...")
bench = dh.top_1000_bench[dh.top_1000_bench['date'] >= pd.Timestamp(start_date)]
bench['nav'] = bench['index_value'] / bench['index_value'].iloc[0] * 100

# ── 2. Calculate Shareholder Breadth per Segment ──────────────────────────────
print("Calculating Shareholder Breadth for all segments...")

# Use quarterly rebalance dates for breadth calculation to match reporting cycles
rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

def get_breadth(date, segment_type):
    u = dh.get_universe(date, 1000)
    if u.empty: return np.nan
    u = u.sort_values('mc', ascending=False)
    
    if segment_type == 'Top200':
        isins = set(u.iloc[:200]['isin'].tolist())
    elif segment_type == '201-1000':
        isins = set(u.iloc[200:]['isin'].tolist()) if len(u) > 200 else set()
    elif segment_type == 'All':
        # For 'All', we use the shareholding_df itself since it contains all reported stocks
        # We need the quarter label for this date (with 1-week lag)
        signal_date = date - pd.Timedelta(days=7)
        # Helper to get quarter label (same logic as DataHandler)
        year, month = signal_date.year, signal_date.month
        if month >= 2 and month < 5:    q, prev_q = f"Dec-{year-1}", f"Dec-{year-2}"
        elif month >= 5 and month < 8:  q, prev_q = f"Mar-{year}", f"Mar-{year-1}"
        elif month >= 8 and month < 11: q, prev_q = f"Jun-{year}", f"Jun-{year-1}"
        else:                           q, prev_q = f"Sep-{year}", f"Sep-{year-1}"
        
        curr_slice = dh.shareholding_df[dh.shareholding_df['quarter'] == q].set_index('isin')['total_shareholders']
        prev_slice = dh.shareholding_df[dh.shareholding_df['quarter'] == prev_q].set_index('isin')['total_shareholders']
        if curr_slice.empty or prev_slice.empty: return np.nan
        
        merged = pd.concat([curr_slice, prev_slice], axis=1, keys=['curr', 'prev']).dropna()
        return (merged['curr'] < merged['prev']).mean() * 100

    if not isins: return np.nan

    # For segmented cases, use get_shareholder_trend (which has the 1-week lag built into our logic)
    signal_date = date - pd.Timedelta(days=7)
    actual_signal = max([dt for dt in all_dates if dt <= signal_date])
    sh_trend = dh.get_shareholder_trend(actual_signal, lookback_quarters=4)
    if sh_trend.empty: return np.nan
    
    sh_seg = sh_trend[sh_trend['isin'].isin(isins)]
    if sh_seg.empty: return np.nan
    return sh_seg['decreased'].mean() * 100

breadth_data = []
for d in rdates:
    b200 = get_breadth(d, 'Top200')
    bMid = get_breadth(d, '201-1000')
    bAll = get_breadth(d, 'All')
    breadth_data.append({
        'date': d,
        'b200': b200,
        'bMid': bMid,
        'bAll': bAll
    })

b_df = pd.DataFrame(breadth_data)

# ── 3. Plotting ───────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#0d1117')

# Left Axis: Top 1000 NAV
l1, = ax1.plot(bench['date'], bench['nav'], color='#ffffff', linewidth=3, alpha=0.9, label='Top 1000 Benchmark')
ax1.set_ylabel("Top 1000 Benchmark NAV (base=100)", color='white', fontsize=12)
ax1.tick_params(axis='y', colors='white')
ax1.grid(True, color='#1e1e2e', linewidth=0.8)

# Right Axis: Breadth %
ax2 = ax1.twinx()
l2, = ax2.plot(b_df['date'], b_df['b200'], color='#00d4ff', linewidth=2, label='SH Breadth % (Top 200)')
l3, = ax2.plot(b_df['date'], b_df['bMid'], color='#ff9500', linewidth=2, label='SH Breadth % (201-1000)')
l4, = ax2.plot(b_df['date'], b_df['bAll'], color='#00ff88', linewidth=2, linestyle='--', alpha=0.8, label='SH Breadth % (All Stocks)')

ax2.set_ylabel("Shareholder Breadth % (stocks with ↓ SH)", color='#aaaaaa', fontsize=12)
ax2.tick_params(axis='y', colors='#aaaaaa')
ax2.set_ylim(0, 100)

# Reference line at 50%
ax2.axhline(50, color='#555555', linewidth=1, linestyle=':', alpha=0.8)

# Legends
all_lines = [l1, l2, l3, l4]
ax1.legend(handles=all_lines, facecolor='#1a1a2e', labelcolor='white', loc='upper left', fontsize=10)

ax1.set_title("Market Breadth Comparison: Multi-Segment Shareholder Trends vs Top 1000", color='white', fontsize=16, pad=20)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.tick_params(axis='x', colors='white')

plt.tight_layout()
out_path = repo_root / "multi_segment_breadth_comparison.png"
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved to: {out_path}")
