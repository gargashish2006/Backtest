"""
MCPS Universe Size Analysis:
Compares performance of 12-stock MCPS12-4Q strategy across:
1. Universe: Top 1000 by Market Cap (Current Baseline)
2. Universe: Top 500 by Market Cap (More Restrictive)
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.mcps15_strategy import MCPSStrategy
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

def run_universe_test(name, universe_size):
    print(f"\n>>> Running: {name} (Universe={universe_size})...")
    p = Portfolio(10_000_000)
    # Using MCPSStrategy with final params, varying universe_size
    s = MCPSStrategy(dh, group_top_pct=0.50, num_stocks=12, max_per_industry=3, 
                     mcps_lookback_quarters=4, universe_size=universe_size)
    s.precompute_rsi(rdates)
    
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav

# ── Run Tests ────────────────────────────────────────────────────────────────
stats_1000, nav_1000 = run_universe_test("MCPS-1000", 1000)
stats_500, nav_500 = run_universe_test("MCPS-500", 500)

# ── Print Summary ────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print(f"{'Metric':<20} | {'Top 1000':^12} | {'Top 500':^12}")
print("-" * 50)
for k in stats_1000.keys():
    print(f"{k:<20} | {stats_1000[k]:^12} | {stats_500[k]:^12}")
print("=" * 50)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(nav_1000.index, nav_1000.values, color='#6bcb77', linewidth=2, label=f"Top 1000 | CAGR {stats_1000['CAGR']}")
ax.plot(nav_500.index, nav_500.values, color='#ff6b6b', linewidth=2, label=f"Top 500 | CAGR {stats_500['CAGR']}")

ax.set_title("MCPS Universe Size Comparison (Top 1000 vs Top 500)", color='white', pad=20)
ax.tick_params(colors='white')
for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222')
ax.legend(facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "mcps_universe_comparison.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
