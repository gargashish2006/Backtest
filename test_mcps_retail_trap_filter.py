"""
MCPS15 Retail Trap Filter Analysis:
Tests group_top_pct thresholds: 40%, 50%, 60%.
Adds a stock-level filter: Exclude stock if (M-Cap Down AND Shareholders Up).
Note: This is equivalent to excluding stocks with negative MCPS change where both components moved adversely.
Uses cleaned price data and MCPS15Strategy v2 logic.
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

class MCPS15RetailTrapStrategy(MCPS15Strategy):
    """
    Subclass of MCPS15Strategy that adds the 'Retail Trap' filter at stock level.
    Retail Trap = (Market Cap Down) AND (Shareholders Up).
    We exclude these stocks from the selection pool.
    """
    def calculate_selection(self, date: pd.Timestamp):
        # 1. Signal date (T-7)
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        sh_df = self.dh.shareholding_df
        if sh_df is None or sh_df.empty:
            return {}

        curr_q, prev_q = self._get_quarter_labels(actual_signal_date)
        curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(
            columns={'total_shareholders': 'curr_sh'})
        prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(
            columns={'total_shareholders': 'prev_sh'})
        if curr_sh.empty or prev_sh.empty:
            return {}

        merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        merged = merged[(merged['curr_sh'] > 0) & (merged['prev_sh'] > 0)]
        merged['group'] = merged['isin'].map(self.dh.isin_to_group)
        merged['industry'] = merged['isin'].map(self.dh.isin_to_industry)
        merged = merged.dropna(subset=['group', 'industry'])

        # Group Breadth Filter
        merged['decreased'] = merged['curr_sh'] < merged['prev_sh']
        group_stats = merged.groupby('group')['decreased'].mean().reset_index()
        n_top = max(1, int(len(group_stats) * self.group_top_pct))
        top_groups = group_stats.sort_values('decreased', ascending=False).head(n_top)['group'].tolist()
        merged = merged[merged['group'].isin(top_groups)]
        if merged.empty:
            return {}

        # M-Cap and MCPS
        mc_now = self._get_mc_on_date(actual_signal_date)
        mc_prev = self._get_mc_on_date(actual_signal_date - pd.DateOffset(years=1))
        
        merged = merged.copy()
        merged['mc_now'] = merged['isin'].map(mc_now)
        merged['mc_prev'] = merged['isin'].map(mc_prev)
        merged = merged.dropna(subset=['mc_now', 'mc_prev'])
        merged = merged[(merged['mc_now'] > 0) & (merged['mc_prev'] > 0)]
        
        merged['mcps_now'] = merged['mc_now'] / merged['curr_sh']
        merged['mcps_prev'] = merged['mc_prev'] / merged['prev_sh']
        merged['mcps_positive'] = merged['mcps_now'] > merged['mcps_prev']

        # Industry Ranking
        ind_ranked = (merged.groupby('industry')
                      .agg(mcps_positive_pct=('mcps_positive', 'mean'))
                      .reset_index()
                      .sort_values('mcps_positive_pct', ascending=False))

        # IDENTIFY RETAIL TRAPS for filtering
        # Retail Trap = (mc_now < mc_prev) AND (curr_sh > prev_sh)
        merged['retail_trap'] = (merged['mc_now'] < merged['mc_prev']) & (merged['curr_sh'] > merged['prev_sh'])
        retail_trap_isins = set(merged[merged['retail_trap']]['isin'])

        # Universe and Filters
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty:
            return {}

        # Apply stock-level filter: Exclude retail traps
        universe = universe[~universe['isin'].isin(retail_trap_isins)]

        # Median Liquidity
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # RSI Entry
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        # Selection
        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            for isin in ind_stocks.head(self.max_per_industry)['isin']:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break

        if not selected: return {}
        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()
rdates = sorted([max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
                for y in range(2017, 2027) for m in [2, 5, 8, 11]
                if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
fee_model = FeeModel(0.0015, 0.005)

def run_variant(label, group_pct, use_filter=True):
    print(f"Running {label}...")
    p = Portfolio(10_000_000)
    if use_filter:
        s = MCPS15RetailTrapStrategy(dh, group_top_pct=group_pct)
    else:
        s = MCPS15Strategy(dh, group_top_pct=group_pct)
    s.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125), cash_yield_rate=0.05, cash_tax_rate=0.30)
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
e0 = SimEngine(dh, p0, fee_model, TaxManager(0.20, 0.125), cash_yield_rate=0.05, cash_tax_rate=0.30)
e0.run(start_date, end_date, s0.calculate_selection, rdates, verbose=False)
cs15_stats = calculate_metrics(pd.DataFrame(p0.nav_history))
cs15_nav = pd.DataFrame(p0.nav_history).set_index('date')['nav']
cs15_nav = cs15_nav / cs15_nav.iloc[0] * 100

# ── Run Variants ──────────────────────────────────────────────────────────────
variants = [
    ("MCPS15-B Group 50% (No Filter)", 0.50, False),
    ("MCPS15-B Group 40% + RT Filter", 0.40, True),
    ("MCPS15-B Group 50% + RT Filter", 0.50, True),
    ("MCPS15-B Group 60% + RT Filter", 0.60, True),
]

results = {}
nav_history = {}
for label, g_pct, use_f in variants:
    stats, nav = run_variant(label, g_pct, use_f)
    results[label] = stats
    nav_history[label] = nav

# ── Print Table ───────────────────────────────────────────────────────────────
print("\n" + "=" * 120)
header = f"{'Metric':<20} | {'CS15':^12} | " + " | ".join(f"{l[:15]:^15}" for l, _, _ in variants)
print(header)
print("-" * 120)
for k in cs15_stats.keys():
    row = f"{k:<20} | {cs15_stats[k]:^12} | "
    row += " | ".join(f"{results[label].get(k,'N/A'):^15}" for label, _, _ in variants)
    print(row)
print("=" * 120)

# ── Plot ──────────────────────────────────────────────────────────────────────
colors = ['#888888', '#ff6b6b', '#6bcb77', '#4d96ff']
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')
ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=3, label=f"CS15 | {cs15_stats['CAGR']}")
for (label, _, _), color in zip(variants, colors):
    ax.plot(nav_history[label].index, nav_history[label].values, color=color, linewidth=1.5, label=f"{label} | {results[label]['CAGR']}")
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.tick_params(colors='#aaaaaa')
ax.grid(True, color='#222222')
ax.legend(loc='upper left', fontsize=9, framealpha=0.2, facecolor='#1a1a2e', labelcolor='white')
plt.tight_layout()
plt.savefig(repo_root / "mcps15_retail_trap_analysis.png", dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {repo_root / 'mcps15_retail_trap_analysis.png'}")
