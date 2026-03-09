"""
CS15 vs MCPS12-4Q Comparative Analysis
Calculates performance, correlation, and overlap between the two strategies.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
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

def run_strategy(name, strategy_obj):
    print(f"Running {name}...")
    p = Portfolio(10_000_000)
    strategy_obj.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, strategy_obj.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    
    # Store holdings for overlap calculation
    # SimEngine records holdings in e.rebalance_history or similar? 
    # Let's just track them here by re-running selection
    holdings_history = {}
    for rd in rdates:
        holdings_history[rd] = set(strategy_obj.calculate_selection(rd).keys())
        
    return stats, nav, holdings_history

# ── Run CS15 ──────────────────────────────────────────────────────────────────
cs15_strategy = CS15Strategy(dh)
cs15_stats, cs15_nav, cs15_holdings = run_strategy("CS15", cs15_strategy)

# ── Run MCPS12-4Q ─────────────────────────────────────────────────────────────
mcps12_strategy = MCPSStrategy(dh, num_stocks=12)
mcps12_stats, mcps12_nav, mcps12_holdings = run_strategy("MCPS12", mcps12_strategy)

# ── Calculate Correlation ─────────────────────────────────────────────────────
# Returns correlation (Daily)
cs15_rets = cs15_nav.pct_change().dropna()
mcps12_rets = mcps12_nav.pct_change().dropna()
common_dates = cs15_rets.index.intersection(mcps12_rets.index)
correlation = cs15_rets.loc[common_dates].corr(mcps12_rets.loc[common_dates])

# ── Calculate Overlap ─────────────────────────────────────────────────────────
overlaps = []
for rd in rdates:
    h1 = cs15_holdings[rd]
    h2 = mcps12_holdings[rd]
    if h1 or h2:
        overlap_count = len(h1.intersection(h2))
        union_count = len(h1.union(h2))
        overlaps.append(overlap_count / union_count if union_count > 0 else 0)

avg_overlap = np.mean(overlaps) if overlaps else 0

# ── Print Stats ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"{'Metric':<20} | {'CS15':^15} | {'MCPS12-4Q':^15}")
print("-" * 60)
for k in cs15_stats.keys():
    print(f"{k:<20} | {cs15_stats[k]:^15} | {mcps12_stats[k]:^15}")
print("-" * 60)
print(f"{'Returns Correlation':<20} | {correlation:^33.4f}")
print(f"{'Avg Holding Overlap':<20} | {avg_overlap*100:^32.2f}%")
print("=" * 60)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

# Normalize for plotting
nav_cs15_norm = cs15_nav / cs15_nav.iloc[0] * 100
nav_mcps_norm = mcps12_nav / mcps12_nav.iloc[0] * 100

ax.plot(nav_cs15_norm.index, nav_cs15_norm.values, color='#00d4ff', linewidth=2, label=f"CS15 (Momentum) | CAGR {cs15_stats['CAGR']}")
ax.plot(nav_mcps_norm.index, nav_mcps_norm.values, color='#6bcb77', linewidth=2, label=f"MCPS12 (Shareholder) | CAGR {mcps12_stats['CAGR']}")

ax.set_title('Comparative Analysis: CS15 vs MCPS12-4Q', fontsize=16, color='white', pad=20)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.tick_params(colors='#aaaaaa')
for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222')
ax.legend(loc='upper left', fontsize=10, framealpha=0.2, facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "cs15_vs_mcps12_comparison.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
