"""
Combined Chart: MCPS12 (Top 250) vs MCPS12 (Ex-250)
with Shareholder Breadth % for each segment.

4 series on a dual-axis chart:
  Left Y:  MCPS12 (Top 250) NAV, MCPS12 (Ex-250) NAV
  Right Y: SH Breadth % Top 250, SH Breadth % Ex-250
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import warnings
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.mcps15_strategy import MCPS15Strategy
from utils.analytics import calculate_metrics

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = sorted(dh.get_all_dates())

rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

# ── Segment Simulation ────────────────────────────────────────────────────────
def run_segment(segment_name):
    print(f"Running MCPS12 [{segment_name}]...")
    original_get_universe = dh.get_universe

    def patched(d, size):
        u = original_get_universe(d, 1000)
        if u.empty: return u
        u = u.sort_values('mc', ascending=False)
        if segment_name == 'Top250':
            return u.iloc[:250]
        else:
            return u.iloc[250:] if len(u) > 250 else pd.DataFrame()

    dh.get_universe = patched
    try:
        strat = MCPS15Strategy(dh, group_top_pct=0.50, num_stocks=12, max_per_industry=3)
        strat.precompute_rsi(rdates)
        port = Portfolio(10_000_000)
        eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125),
                        cash_yield_rate=0.05, cash_tax_rate=0.30)
        eng.run(start_date, end_date, strat.calculate_selection, rdates, verbose=False)
    finally:
        dh.get_universe = original_get_universe

    return pd.DataFrame(port.nav_history)

nav_top250 = run_segment('Top250')
nav_ex250  = run_segment('Ex250')

# ── Shareholder Breadth per Segment ──────────────────────────────────────────
print("Calculating Shareholder Breadth per segment...")

def get_segment_breadth(rebalance_dates, segment_name):
    records = []
    for d in rebalance_dates:
        # Get full universe sorted by MC
        u = dh.get_universe(d, 1000)
        if u.empty: continue
        u = u.sort_values('mc', ascending=False)

        if segment_name == 'Top250':
            seg_isins = set(u.iloc[:250]['isin'].tolist())
        else:
            seg_isins = set(u.iloc[250:]['isin'].tolist()) if len(u) > 250 else set()

        if not seg_isins: continue

        # Get shareholder trend for the signal date (7-day lag)
        signal_date = d - pd.Timedelta(days=7)
        actual_signal = max([dt for dt in all_dates if dt <= signal_date])
        sh_trend = dh.get_shareholder_trend(actual_signal, lookback_quarters=4)
        if sh_trend.empty: continue

        # Filter to segment
        sh_seg = sh_trend[sh_trend['isin'].isin(seg_isins)]
        if sh_seg.empty: continue

        breadth_pct = sh_seg['decreased'].mean() * 100  # % with decreasing SH
        records.append({'date': d, 'breadth_pct': breadth_pct})

    return pd.DataFrame(records)

breadth_top250 = get_segment_breadth(rdates, 'Top250')
breadth_ex250  = get_segment_breadth(rdates, 'Ex250')

# ── Metrics ───────────────────────────────────────────────────────────────────
m_top250 = calculate_metrics(nav_top250)
m_ex250  = calculate_metrics(nav_ex250)

print(f"\nTop 250  — CAGR: {m_top250['CAGR']}, MaxDD: {m_top250['Max Drawdown']}, Sharpe: {m_top250['Sharpe Ratio']}")
print(f"Ex-250   — CAGR: {m_ex250['CAGR']}, MaxDD: {m_ex250['Max Drawdown']}, Sharpe: {m_ex250['Sharpe Ratio']}")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(16, 9))
fig.patch.set_facecolor('#0d1117')
ax1.set_facecolor('#0d1117')

# Left axis: NAV
nav_t250_norm = nav_top250.set_index('date')['nav'] / nav_top250['nav'].iloc[0] * 100
nav_ex250_norm = nav_ex250.set_index('date')['nav'] / nav_ex250['nav'].iloc[0] * 100

l1, = ax1.plot(nav_t250_norm.index, nav_t250_norm.values,
               color='#00d4ff', linewidth=2.5,
               label=f"MCPS12 Top 250 | CAGR {m_top250['CAGR']} | MaxDD {m_top250['Max Drawdown']}")
l2, = ax1.plot(nav_ex250_norm.index, nav_ex250_norm.values,
               color='#ff9500', linewidth=2.5,
               label=f"MCPS12 Ex-250 | CAGR {m_ex250['CAGR']} | MaxDD {m_ex250['Max Drawdown']}")

ax1.set_ylabel("Normalized NAV (base=100)", color='white', fontsize=12)
ax1.tick_params(axis='y', colors='white')
ax1.tick_params(axis='x', colors='white')
ax1.grid(True, color='#1e1e2e', linewidth=0.8)

# Right axis: Breadth %
ax2 = ax1.twinx()
ax2.set_facecolor('#0d1117')

l3, = ax2.plot(breadth_top250['date'], breadth_top250['breadth_pct'],
               color='#00d4ff', linewidth=1.5, linestyle='--', alpha=0.7,
               label="SH Breadth % Top 250")
l4, = ax2.plot(breadth_ex250['date'], breadth_ex250['breadth_pct'],
               color='#ff9500', linewidth=1.5, linestyle='--', alpha=0.7,
               label="SH Breadth % Ex-250")

ax2.set_ylabel("Shareholder Breadth % (stocks with ↓ SH)", color='#aaaaaa', fontsize=11)
ax2.tick_params(axis='y', colors='#aaaaaa')
ax2.set_ylim(0, 100)

# Add 50% reference line on right axis
ax2.axhline(50, color='#555555', linewidth=1, linestyle=':', alpha=0.8)
ax2.text(breadth_top250['date'].iloc[0], 51, '50% Threshold', color='#777777', fontsize=9)

# Combined legend
all_lines = [l1, l2, l3, l4]
ax1.legend(handles=all_lines, facecolor='#1a1a2e', labelcolor='white',
           loc='upper left', fontsize=10, framealpha=0.9)

ax1.set_title("MCPS12: Segment Performance vs Shareholder Breadth\n(Top 250 vs Rank 251-1000)",
              color='white', fontsize=16, pad=15)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax1.xaxis.set_major_locator(mdates.YearLocator())

plt.tight_layout()
out_path = repo_root / "mcps12_segments_breadth_overlay.png"
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved to: {out_path}")
