"""
MCPS15 Sensitivity: Test 70%, 50%, 30% MCPS positive % threshold
No changes to original files — uses inline subclass override.
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
fee_model = FeeModel(0.0015, 0.005)


class MCPS15Threshold(MCPS15Strategy):
    """MCPS15 with a minimum MCPS positive % threshold to qualify an industry."""

    def __init__(self, data_handler, min_mcps_pct: float = 0.0, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.min_mcps_pct = min_mcps_pct

    def calculate_selection(self, date: pd.Timestamp):
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # MCPS ranking — apply threshold filter
        ind_ranked = self._get_mcps_ranking(actual_signal_date)
        if ind_ranked.empty:
            return {}
        # Apply threshold: only industries where >= min_mcps_pct of stocks show positive MCPS
        ind_ranked = ind_ranked[ind_ranked['mcps_positive_pct'] >= self.min_mcps_pct]
        if ind_ranked.empty:
            return {}

        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty:
            return {}

        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = (liq_df.groupby('isin')['traded_val']
                   .median().reset_index()
                   .rename(columns={'traded_val': 'med_val_21d'}))
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = (universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                          .sort_values('mc', ascending=False))
            for isin in ind_stocks.head(self.max_per_industry)['isin']:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= self.num_stocks:
                        break
            if len(selected) >= self.num_stocks:
                break

        if not selected:
            return {}

        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}


def run_variant(label, min_pct):
    print(f"Running MCPS15 (threshold >= {int(min_pct*100)}%)...")
    p = Portfolio(10_000_000)
    s = MCPS15Threshold(dh, min_mcps_pct=min_pct)
    s.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)
    stats = calculate_metrics(pd.DataFrame(p.nav_history))
    nav = pd.DataFrame(p.nav_history).set_index('date')['nav']
    nav = nav / nav.iloc[0] * 100
    return stats, nav


# ── CS15 baseline ─────────────────────────────────────────────────────────────
print("\nRunning CS15 (baseline)...")
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

# ── Run all variants ──────────────────────────────────────────────────────────
variants = [
    ("MCPS15 (no filter)", 0.0),
    ("MCPS15 >= 30%",      0.30),
    ("MCPS15 >= 50%",      0.50),
    ("MCPS15 >= 70%",      0.70),
]
results = {}
navs    = {}
for label, pct in variants:
    stats, nav = run_variant(label, pct)
    results[label] = stats
    navs[label]    = nav

# ── Print table ───────────────────────────────────────────────────────────────
print("\n" + "=" * 95)
header = f"{'Metric':<22} | {'CS15':^18} | " + " | ".join(f"{l:^18}" for l, _ in variants)
print(header)
print("-" * 95)
for k in cs15_stats.keys():
    row = f"{k:<22} | {cs15_stats[k]:^18} | "
    row += " | ".join(f"{results[l].get(k,'N/A'):^18}" for l, _ in variants)
    print(row)
print(f"{'Benchmark CAGR':<22} | {bench_cagr*100:.2f}%")
print("=" * 95)

# ── Plot ──────────────────────────────────────────────────────────────────────
colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff']
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=2.5,
        label=f"CS15 | CAGR {cs15_stats['CAGR']} | Sharpe {cs15_stats['Sharpe Ratio']}")
for (label, _), color in zip(variants, colors):
    s = results[label]
    ax.plot(navs[label].index, navs[label].values, color=color, linewidth=1.8,
            label=f"{label} | CAGR {s['CAGR']} | Sharpe {s['Sharpe Ratio']}")
ax.plot(bench_nav.index, bench_nav.values, color='#888888', linewidth=1.2,
        linestyle='--', label=f"Benchmark | CAGR {bench_cagr*100:.2f}%")

ax.set_title('MCPS15 Threshold Sensitivity vs CS15', fontsize=16,
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
ax.legend(loc='upper left', fontsize=9, framealpha=0.2,
          facecolor='#1a1a2e', edgecolor='#333333', labelcolor='white')

out_path = repo_root / "mcps15_threshold_sensitivity.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"\nSaved to: {out_path}")
plt.show()
