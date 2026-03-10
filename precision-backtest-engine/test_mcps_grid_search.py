import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
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

# Matrix setup
num_stocks_list = [9, 12, 15]
group_thresholds = [0.30, 0.40, 0.50, 0.60]
threshold_labels = [f"{g*100:.0f}%" for g in group_thresholds]

results_matrix_cagr = np.zeros((len(num_stocks_list), len(group_thresholds)))
results_matrix_mdd  = np.zeros((len(num_stocks_list), len(group_thresholds)))
flat_results = []

print(f"Starting Grid Search (12 combinations)...")

for i, n in enumerate(num_stocks_list):
    for j, g in enumerate(group_thresholds):
        print(f">>> Running: Stocks={n}, Group={g*100:.0f}%...")
        
        p = Portfolio(10_000_000)
        s = MCPSStrategy(dh, group_top_pct=g, num_stocks=n, max_per_industry=3)
        s.precompute_rsi(rdates)
        
        e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                      cash_yield_rate=0.05, cash_tax_rate=0.30)
        e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
        
        stats = calculate_metrics(pd.DataFrame(p.nav_history))
        cagr = float(stats['CAGR'].replace('%', ''))
        mdd  = float(stats['Max Drawdown'].replace('%', ''))
        
        results_matrix_cagr[i, j] = cagr
        results_matrix_mdd[i, j] = mdd
        flat_results.append({
            'Stocks': n,
            'Group %': f"{g*100:.0f}%",
            'CAGR': cagr,
            'MaxDD': mdd,
            'Sharpe': float(stats['Sharpe Ratio'])
        })

# ── Print Summary Table ───────────────────────────────────────────────────────
df = pd.DataFrame(flat_results)
print("\n" + "=" * 60)
print(f"{'Stocks':^8} | {'Group %':^10} | {'CAGR':^8} | {'MaxDD':^8} | {'Sharpe':^8}")
print("-" * 60)
for _, row in df.sort_values(['CAGR'], ascending=False).iterrows():
    print(f"{int(row['Stocks']):^8} | {row['Group %']:^10} | {row['CAGR']:^8.2f} | {row['MaxDD']:^8.2f} | {row['Sharpe']:^8.2f}")
print("=" * 60)

# ── Plot Heatmaps (Vanilla Matplotlib) ───────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.patch.set_facecolor('#0d1117')

for ax in [ax1, ax2]:
    ax.set_facecolor('#0d1117')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333333')

# CAGR Heatmap
im1 = ax1.imshow(results_matrix_cagr, cmap='RdYlGn')
ax1.set_title("CAGR Matrix (Stocks vs Group Threshold)", color='white', pad=20)
ax1.set_xticks(np.arange(len(group_thresholds)))
ax1.set_yticks(np.arange(len(num_stocks_list)))
ax1.set_xticklabels(threshold_labels, color='white')
ax1.set_yticklabels(num_stocks_list, color='white')

for i in range(len(num_stocks_list)):
    for j in range(len(group_thresholds)):
        ax1.text(j, i, f"{results_matrix_cagr[i, j]:.1f}%", ha="center", va="center", color="black" if 10 < results_matrix_cagr[i,j] < 18 else "white")

# MaxDD Heatmap
im2 = ax2.imshow(results_matrix_mdd, cmap='RdYlGn_r')
ax2.set_title("Max Drawdown Matrix (Lower is Better)", color='white', pad=20)
ax2.set_xticks(np.arange(len(group_thresholds)))
ax2.set_yticks(np.arange(len(num_stocks_list)))
ax2.set_xticklabels(threshold_labels, color='white')
ax2.set_yticklabels(num_stocks_list, color='white')

for i in range(len(num_stocks_list)):
    for j in range(len(group_thresholds)):
        ax2.text(j, i, f"{results_matrix_mdd[i, j]:.1f}%", ha="center", va="center", color="black" if results_matrix_mdd[i,j] > -30 else "white")

out_path = repo_root / "mcps_grid_search_analysis.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
