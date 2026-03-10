"""
Plot CS15 NAV vs Top 1000 Benchmark (frictionless, no cost/tax)
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
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data.parquet")
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

# ── CS15 (with post-tax costs) ────────────────────────────────────────────────
print("Running CS15...")
fee_model  = FeeModel(0.0015, 0.005)
tax_man    = TaxManager(0.20, 0.125)
portfolio  = Portfolio(10_000_000)
strategy   = CS15Strategy(dh)
strategy.precompute_rsi(rdates)
engine     = SimEngine(dh, portfolio, fee_model, tax_man,
                       cash_yield_rate=0.05, cash_tax_rate=0.30)
engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)

cs15_nav = pd.DataFrame(portfolio.nav_history).set_index('date')['nav']
cs15_nav = cs15_nav / cs15_nav.iloc[0] * 100   # index to 100

# ── Top 1000 Benchmark (frictionless) ────────────────────────────────────────
print("Loading benchmark...")
bench = dh.top_1000_bench.copy()
bench['date'] = pd.to_datetime(bench['date'])
bench = bench[(bench['date'] >= pd.Timestamp(start_date)) &
              (bench['date'] <= pd.Timestamp(end_date))].set_index('date')
bench_nav = bench['index_value'] / bench['index_value'].iloc[0] * 100

# ── Metrics ───────────────────────────────────────────────────────────────────
cs15_stats  = calculate_metrics(pd.DataFrame(portfolio.nav_history))
bench_final = bench_nav.iloc[-1]
bench_years = (bench_nav.index[-1] - bench_nav.index[0]).days / 365.25
bench_cagr  = (bench_final / 100) ** (1 / bench_years) - 1

print(f"\nCS15  — CAGR: {cs15_stats['CAGR']}, Sharpe: {cs15_stats['Sharpe Ratio']}, Max DD: {cs15_stats['Max Drawdown']}")
print(f"Bench — CAGR: {bench_cagr*100:.2f}%")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index,  cs15_nav.values,  color='#00d4ff', linewidth=2.0,
        label=f'CS15  | CAGR {cs15_stats["CAGR"]} | Sharpe {cs15_stats["Sharpe Ratio"]} | DD {cs15_stats["Max Drawdown"]}')
ax.plot(bench_nav.index, bench_nav.values, color='#ff9500', linewidth=1.5,
        linestyle='--', label=f'Top 1000 Benchmark (Frictionless) | CAGR {bench_cagr*100:.2f}%')

ax.fill_between(cs15_nav.index, cs15_nav.values, bench_nav.reindex(cs15_nav.index, method='ffill').values,
                where=(cs15_nav.values > bench_nav.reindex(cs15_nav.index, method='ffill').values),
                alpha=0.08, color='#00d4ff')

ax.set_title('CS15 Strategy vs Top 1000 Benchmark (Frictionless)', fontsize=16,
             color='white', fontweight='bold', pad=15)
ax.set_xlabel('Date', color='#aaaaaa', fontsize=11)
ax.set_ylabel('Indexed NAV (Base = 100)', color='#aaaaaa', fontsize=11)
ax.tick_params(colors='#aaaaaa')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.xaxis.set_major_locator(mdates.YearLocator())
plt.xticks(rotation=30)

for spine in ax.spines.values():
    spine.set_edgecolor('#333333')
ax.grid(True, color='#222222', linewidth=0.5)

legend = ax.legend(loc='upper left', fontsize=9, framealpha=0.2,
                   facecolor='#1a1a2e', edgecolor='#333333', labelcolor='white')

out_path = repo_root / "cs15_vs_benchmark.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"\nSaved to: {out_path}")
plt.show()
