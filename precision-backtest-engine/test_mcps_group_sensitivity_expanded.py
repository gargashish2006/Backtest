"""
MCPS15 Group Breadth Sensitivity Test (Expanded):
Tests group_top_pct thresholds: 50%, 60%, 70%.
Uses the updated MCPS15Strategy (v2) and cleaned price data.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.mcps15_strategy import MCPS15Strategy
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
# Use cleaned data
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()

rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
fee_model = FeeModel(0.0015, 0.005)

def run_variant(label, group_pct):
    print(f"Running {label} (Top {group_pct*100:.0f}% groups)...")
    p = Portfolio(10_000_000)
    s = MCPS15Strategy(dh, group_top_pct=group_pct)
    s.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav

# ── Baseline CS15 ─────────────────────────────────────────────────────────────
print("\nRunning CS15 (Baseline)...")
p0 = Portfolio(10_000_000)
s0 = CS15Strategy(dh)
s0.precompute_rsi(rdates)
e0 = SimEngine(dh, p0, fee_model, TaxManager(0.20, 0.125),
               cash_yield_rate=0.05, cash_tax_rate=0.30)
e0.run(start_date, end_date, s0.calculate_selection, rdates, verbose=False)
cs15_stats = calculate_metrics(pd.DataFrame(p0.nav_history))
cs15_nav = pd.DataFrame(p0.nav_history).set_index('date')['nav']
cs15_nav = cs15_nav / cs15_nav.iloc[0] * 100

# ── Benchmark ─────────────────────────────────────────────────────────────────
bench = dh.top_1000_bench.copy()
bench['date'] = pd.to_datetime(bench['date'])
bench = bench[(bench['date'] >= pd.Timestamp(start_date)) &
              (bench['date'] <= pd.Timestamp(end_date))].set_index('date')
bench_nav = bench['index_value'] / bench['index_value'].iloc[0] * 100
bench_years = (bench_nav.index[-1] - bench_nav.index[0]).days / 365.25
bench_cagr = (bench_nav.iloc[-1] / 100) ** (1 / bench_years) - 1

# ── Run Sensitivity Variants ──────────────────────────────────────────────────
variants = [
    ("MCPS15 Group 50%", 0.50),
    ("MCPS15 Group 60%", 0.60),
    ("MCPS15 Group 70%", 0.70),
]

results = {}
nav_history = {}

for label, threshold in variants:
    stats, nav = run_variant(label, threshold)
    results[label] = stats
    nav_history[label] = nav

# ── Print Table ───────────────────────────────────────────────────────────────
print("\n" + "=" * 100)
header = f"{'Metric':<20} | {'CS15':^12} | " + " | ".join(f"{l:^15}" for l, _ in variants)
print(header)
print("-" * 100)
for k in cs15_stats.keys():
    row = f"{k:<20} | {cs15_stats[k]:^12} | "
    row += " | ".join(f"{results[l].get(k,'N/A'):^15}" for l, _ in variants)
    print(row)
print(f"{'Benchmark CAGR':<20} | {bench_cagr*100:.2f}%")
print("=" * 100)

# ── Plot ──────────────────────────────────────────────────────────────────────
colors = ['#6bcb77', '#4d96ff', '#a06ee1']
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=3,
        label=f"CS15 | CAGR {cs15_stats['CAGR']} | Sharpe {cs15_stats['Sharpe Ratio']}")

for (label, _), color in zip(variants, colors):
    s = results[label]
    ax.plot(nav_history[label].index, nav_history[label].values, color=color, linewidth=1.5,
            label=f"{label} | CAGR {s['CAGR']} | Sharpe {s['Sharpe Ratio']}")

ax.plot(bench_nav.index, bench_nav.values, color='#888888', linewidth=1,
        linestyle='--', label=f"Bench | CAGR {bench_cagr*100:.2f}%")

ax.set_title('MCPS15 Group Breadth Sensitivity (50%, 60%, 70%)', fontsize=16, color='white', pad=20)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.tick_params(colors='#aaaaaa')
for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222')
ax.legend(loc='upper left', fontsize=9, framealpha=0.2, facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "mcps15_group_sensitivity_expanded.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved sensitivity plot to: {out_path}")
plt.show()
