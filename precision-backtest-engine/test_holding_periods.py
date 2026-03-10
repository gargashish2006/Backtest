"""
Rebalance Frequency & Seasonality Analysis: 
Tests 6-month holding periods (Feb-Aug vs May-Nov) for CS15 and MCPS12.
"""
import pandas as pd
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

fee_model = FeeModel(0.0015, 0.005)

def get_rebalance_dates(months):
    """Generate rebalance dates for given list of months (e.g. [2, 8])."""
    rdates = sorted([
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2017, 2027) for m in months
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ])
    return [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

def run_test(strategy_name, strategy_obj, months, label):
    print(f"Running {strategy_name} - {label}...")
    rdates = get_rebalance_dates(months)
    p = Portfolio(10_000_000)
    strategy_obj.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, strategy_obj.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav

# ── Backtest Matrix ───────────────────────────────────────────────────────────
scenarios = [
    # CS15 Variations
    ("CS15", CS15Strategy(dh), [2, 5, 8, 11], "Quarterly"),
    ("CS15", CS15Strategy(dh), [2, 8],       "6M (Feb-Aug)"),
    ("CS15", CS15Strategy(dh), [5, 11],      "6M (May-Nov)"),
    
    # MCPS12 Variations
    ("MCPS12", MCPSStrategy(dh, num_stocks=12), [2, 5, 8, 11], "Quarterly"),
    ("MCPS12", MCPSStrategy(dh, num_stocks=12), [2, 8],       "6M (Feb-Aug)"),
    ("MCPS12", MCPSStrategy(dh, num_stocks=12), [5, 11],      "6M (May-Nov)"),
]

results = []
navs = {}

for s_name, s_obj, months, label in scenarios:
    stats, nav = run_test(s_name, s_obj, months, label)
    key = f"{s_name} {label}"
    results.append({
        "Strategy": s_name,
        "Schedule": label,
        "CAGR": stats["CAGR"],
        "Max DD": stats["Max Drawdown"],
        "Sharpe": stats["Sharpe Ratio"]
    })
    navs[key] = nav

# ── Print Table ───────────────────────────────────────────────────────────────
df_res = pd.DataFrame(results)
print("\n" + "=" * 80)
print(f"{'Strategy':<10} | {'Schedule':<15} | {'CAGR':^10} | {'Max DD':^10} | {'Sharpe':^10}")
print("-" * 80)
for _, row in df_res.iterrows():
    print(f"{row['Strategy']:<10} | {row['Schedule']:<15} | {row['CAGR']:^10} | {row['Max DD']:^10} | {row['Sharpe']:^10}")
print("=" * 80)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)
fig.patch.set_facecolor('#0d1117')

def setup_ax(ax, title):
    ax.set_facecolor('#0d1117')
    ax.set_title(title, color='white', fontsize=14, pad=15)
    ax.tick_params(colors='#aaaaaa')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333333')
    ax.grid(True, color='#222222')

setup_ax(ax1, "CS15 Holding Period Variations")
setup_ax(ax2, "MCPS12 Holding Period Variations")

# Plot CS15
colors_cs = ['#00d4ff', '#0096ff', '#0056ff']
for i, label in enumerate(["Quarterly", "6M (Feb-Aug)", "6M (May-Nov)"]):
    key = f"CS15 {label}"
    ax1.plot(navs[key].index, navs[key].values, color=colors_cs[i], linewidth=2, label=f"{label} | CAGR {df_res[df_res['Strategy']=='CS15'].iloc[i]['CAGR']}")

# Plot MCPS12
colors_mc = ['#6bcb77', '#34a853', '#1b5e20']
for i, label in enumerate(["Quarterly", "6M (Feb-Aug)", "6M (May-Nov)"]):
    key = f"MCPS12 {label}"
    ax2.plot(navs[key].index, navs[key].values, color=colors_mc[i], linewidth=2, label=f"{label} | CAGR {df_res[df_res['Strategy']=='MCPS12'].iloc[i]['CAGR']}")

ax1.legend(loc='upper left', facecolor='#1a1a2e', labelcolor='white')
ax2.legend(loc='upper left', facecolor='#1a1a2e', labelcolor='white')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

out_path = repo_root / "holding_period_variations.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
