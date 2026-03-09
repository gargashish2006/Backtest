"""
MCPS Lookback Sensitivity Analysis:
Tests MCPS (12 stocks) with different signal lookbacks (2Q, 3Q, 4Q, 5Q).
Industry group filter is fixed at a 4Q lookback.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.mcps15_strategy import MCPSStrategy
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
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

def run_lookback(label, lookback_q):
    print(f"Running {label} (lookback={lookback_q}Q)...")
    p = Portfolio(10_000_000)
    # Using MCPSStrategy (12 stocks, 3 max per industry)
    s = MCPSStrategy(dh, group_top_pct=0.50, num_stocks=12, max_per_industry=3, 
                     mcps_lookback_quarters=lookback_q)
    s.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav

# ── Run Lookbacks ─────────────────────────────────────────────────────────────
results = {}
nav_history = {}

for q in [2, 3, 4, 5]:
    label = f"MCPS ({q}Q)"
    stats, nav = run_lookback(label, q)
    results[label] = stats
    nav_history[label] = nav

# ── Baseline CS15 for Reference (15 Stocks) ───────────────────────────────────
print("\nRunning CS15 (Benchmark - 15 Stocks)...")
p0 = Portfolio(10_000_000)
s0 = CS15Strategy(dh)
s0.precompute_rsi(rdates)
e0 = SimEngine(dh, p0, fee_model, TaxManager(0.20, 0.125),
               cash_yield_rate=0.05, cash_tax_rate=0.30)
e0.run(start_date, end_date, s0.calculate_selection, rdates, verbose=False)
cs15_stats = calculate_metrics(pd.DataFrame(p0.nav_history))
cs15_nav = pd.DataFrame(p0.nav_history).set_index('date')['nav']
cs15_nav = cs15_nav / cs15_nav.iloc[0] * 100

# ── Print Table ───────────────────────────────────────────────────────────────
print("\n" + "=" * 90)
header = f"{'Metric':<20} | {'CS15':^12} | " + " | ".join(f"{l:^12}" for l in nav_history.keys())
print(header)
print("-" * 90)
for k in cs15_stats.keys():
    row = f"{k:<20} | {cs15_stats[k]:^12} | "
    row += " | ".join(f"{results[label][k]:^12}" for label in nav_history.keys())
    print(row)
print("=" * 90)

# ── Plot ──────────────────────────────────────────────────────────────────────
colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff']
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=2, linestyle='--',
        label=f"CS15 | CAGR {cs15_stats['CAGR']}")

for label, color in zip(nav_history.keys(), colors):
    ax.plot(nav_history[label].index, nav_history[label].values, color=color, linewidth=2,
            label=f"{label} | CAGR {results[label]['CAGR']}")

ax.set_title('MCPS Lookback Sensitivity Analysis (2Q - 5Q)', fontsize=16, color='white', pad=20)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.tick_params(colors='#aaaaaa')
for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222')
ax.legend(loc='upper left', fontsize=10, framealpha=0.2, facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "mcps_lookback_sensitivity_analysis.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
