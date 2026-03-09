"""
MCPS15 Industry Concentration Analysis:
Compares max_per_industry=3 (baseline) vs max_per_industry=5.
Uses MCPS15Strategy v2 (Variant B, Group Top 50%) and cleaned price data.
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

def run_variant(label, max_ind):
    print(f"Running {label} (max_per_industry={max_ind})...")
    p = Portfolio(10_000_000)
    s = MCPS15Strategy(dh, group_top_pct=0.50, max_per_industry=max_ind)
    s.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav

# ── Run Baseline (max 3) ──────────────────────────────────────────────────────
stats_3, nav_3 = run_variant("MCPS15 Max 3", 3)

# ── Run Test (max 5) ──────────────────────────────────────────────────────────
stats_5, nav_5 = run_variant("MCPS15 Max 5", 5)

# ── Baseline CS15 for Reference ───────────────────────────────────────────────
print("\nRunning CS15 (Benchmark)...")
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
print("\n" + "=" * 80)
print(f"{'Metric':<20} | {'CS15':^12} | {'MCPS Max 3':^12} | {'MCPS Max 5':^12}")
print("-" * 80)
for k in cs15_stats.keys():
    print(f"{k:<20} | {cs15_stats[k]:^12} | {stats_3[k]:^12} | {stats_5[k]:^12}")
print("=" * 80)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=2, linestyle='--',
        label=f"CS15 | CAGR {cs15_stats['CAGR']}")
ax.plot(nav_3.index, nav_3.values, color='#6bcb77', linewidth=2.5,
        label=f"MCPS Max 3 | CAGR {stats_3['CAGR']}")
ax.plot(nav_5.index, nav_5.values, color='#ff6b6b', linewidth=1.5,
        label=f"MCPS Max 5 | CAGR {stats_5['CAGR']}")

ax.set_title('MCPS15 Industry Concentration Analysis (Max 3 vs Max 5)', fontsize=16, color='white', pad=20)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.tick_params(colors='#aaaaaa')
for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222')
ax.legend(loc='upper left', fontsize=10, framealpha=0.2, facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "mcps15_ind_concentration_analysis.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved concentration plot to: {out_path}")
plt.show()
