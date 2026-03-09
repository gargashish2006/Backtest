"""
MCPS15 Variant B + CS15-style Group Top 50% Shareholder Breadth Filter:
1. Rank all industry GROUPS by % of stocks with decreasing shareholders
2. Keep only top 50% of groups
3. Within those groups, rank industries by MCPS positive % (Variant B)
4. Select top 3 stocks by M-Cap per industry, up to 15 total
No RSNP filter. No industry-level breadth filter.
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
fee_model = FeeModel(0.0015, 0.005)


def get_quarter_info(signal_date, lookback_quarters=4):
    year, month = signal_date.year, signal_date.month
    quarters = ["Mar", "Jun", "Sep", "Dec"]
    if month >= 2 and month < 5:    start_code, base_year = "Dec", year - 1
    elif month >= 5 and month < 8:  start_code, base_year = "Mar", year
    elif month >= 8 and month < 11: start_code, base_year = "Jun", year
    else:                           start_code, base_year = "Sep", year
    linear_map = {"Mar": 0, "Jun": 1, "Sep": 2, "Dec": 3}
    linear_curr = base_year * 4 + linear_map[start_code]
    linear_prev = linear_curr - lookback_quarters
    prev_code = quarters[linear_prev % 4]
    prev_year = linear_prev // 4
    return f"{start_code}-{base_year}", f"{prev_code}-{prev_year}"

def get_mc_on_date(target_date, price_df):
    available = price_df[price_df['date'] <= target_date]
    if available.empty: return pd.Series(dtype=float)
    latest = available['date'].max()
    return available[available['date'] == latest].set_index('isin')['mc']


class MCPS15GroupFilter:
    """
    MCPS15-B with CS15-style group top 50% shareholder breadth filter.
    group_top_pct: fraction of top groups to keep (default 0.50 = top 50%)
    """

    def __init__(self, data_handler: DataHandler,
                 group_top_pct: float = 0.50,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 rsi_threshold: float = 40.0,
                 max_weight_per_stock: float = 0.10):
        self.dh = data_handler
        self.group_top_pct = group_top_pct
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.rsi_threshold = rsi_threshold
        self.max_weight_per_stock = max_weight_per_stock
        self.rsi_cache = pd.DataFrame()

    def precompute_rsi(self, dates):
        print(f"Pre-computing Weekly RSI Cache for MCPS15+GroupFilter...")
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        delta = weekly_prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))

    def check_exits(self, current_date, portfolio):
        if self.rsi_cache.empty: return []
        isins = list(portfolio.keys()) if isinstance(portfolio, dict) else portfolio
        valid = [d for d in self.rsi_cache.index if d <= current_date]
        if not valid: return []
        rsi_date = max(valid)
        return [i for i in isins
                if i in self.rsi_cache.columns
                and pd.notna(self.rsi_cache.loc[rsi_date, i])
                and self.rsi_cache.loc[rsi_date, i] < 39]

    def calculate_selection(self, date: pd.Timestamp):
        signal_date = date - pd.Timedelta(days=7)
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        sh_df = self.dh.shareholding_df
        if sh_df is None or sh_df.empty: return {}

        curr_q, prev_q = get_quarter_info(actual_signal_date)
        curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin','total_shareholders']].rename(columns={'total_shareholders':'curr_sh'})
        prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin','total_shareholders']].rename(columns={'total_shareholders':'prev_sh'})
        if curr_sh.empty or prev_sh.empty: return {}

        merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        merged = merged[(merged['curr_sh'] > 0) & (merged['prev_sh'] > 0)]
        merged['decreased'] = merged['curr_sh'] < merged['prev_sh']
        merged['group']    = merged['isin'].map(self.dh.isin_to_group)
        merged['industry'] = merged['isin'].map(self.dh.isin_to_industry)
        merged = merged.dropna(subset=['group', 'industry'])

        # Step 1: Group filter — top 50% of groups by shareholder breadth
        group_stats = merged.groupby('group')['decreased'].mean().reset_index()
        n_top = max(1, int(len(group_stats) * self.group_top_pct))
        top_groups = group_stats.sort_values('decreased', ascending=False).head(n_top)['group'].tolist()
        merged_filtered = merged[merged['group'].isin(top_groups)]
        if merged_filtered.empty: return {}

        # Step 2: MCPS ranking (Variant B) within industries from top groups
        mc_now  = get_mc_on_date(actual_signal_date, self.dh.price_df)
        prev_date = actual_signal_date - pd.DateOffset(years=1)
        mc_prev = get_mc_on_date(prev_date, self.dh.price_df)

        merged_filtered = merged_filtered.copy()
        merged_filtered['mc_now']  = merged_filtered['isin'].map(mc_now)
        merged_filtered['mc_prev'] = merged_filtered['isin'].map(mc_prev)
        merged_filtered = merged_filtered.dropna(subset=['mc_now','mc_prev'])
        merged_filtered = merged_filtered[(merged_filtered['mc_now'] > 0) & (merged_filtered['mc_prev'] > 0)]

        merged_filtered['mcps_now']  = merged_filtered['mc_now']  / merged_filtered['curr_sh']
        merged_filtered['mcps_prev'] = merged_filtered['mc_prev'] / merged_filtered['prev_sh']
        merged_filtered['mcps_positive'] = merged_filtered['mcps_now'] > merged_filtered['mcps_prev']

        ind_mcps = (merged_filtered.groupby('industry')
                    .agg(mcps_positive_pct=('mcps_positive', 'mean'))
                    .reset_index()
                    .sort_values('mcps_positive_pct', ascending=False))
        if ind_mcps.empty: return {}

        # Step 3: Universe + liquidity + RSI
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty: return {}

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

        if universe.empty: return {}

        # Step 4: Select top 3 by M-Cap per industry in MCPS rank order
        selected = []
        for ind in ind_mcps['industry']:
            ind_stocks = (universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                          .sort_values('mc', ascending=False))
            for isin in ind_stocks.head(self.max_per_industry)['isin']:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break

        if not selected: return {}
        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}


def run_strategy(label, strategy):
    print(f"Running {label}...")
    p = Portfolio(10_000_000)
    strategy.precompute_rsi(rdates)
    e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
                  cash_yield_rate=0.05, cash_tax_rate=0.30)
    e.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
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

# ── Run variants ──────────────────────────────────────────────────────────────
variants = [
    ("MCPS15-B (no group filter)",      MCPS15GroupFilter(dh, group_top_pct=1.0)),
    ("MCPS15-B + Group Top 50%",        MCPS15GroupFilter(dh, group_top_pct=0.50)),
]
results, navs = {}, {}
for label, strategy in variants:
    stats, nav = run_strategy(label, strategy)
    results[label] = stats
    navs[label]    = nav

# ── Print table ───────────────────────────────────────────────────────────────
print("\n" + "=" * 90)
header = f"{'Metric':<22} | {'CS15':^18} | " + " | ".join(f"{l[:24]:^24}" for l, _ in variants)
print(header)
print("-" * 90)
for k in cs15_stats.keys():
    row = f"{k:<22} | {cs15_stats[k]:^18} | "
    row += " | ".join(f"{results[l].get(k,'N/A'):^24}" for l, _ in variants)
    print(row)
print(f"{'Benchmark CAGR':<22} | {bench_cagr*100:.2f}%")
print("=" * 90)

# ── Plot ──────────────────────────────────────────────────────────────────────
colors = ['#ff9500', '#00ff88']
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(cs15_nav.index, cs15_nav.values, color='#00d4ff', linewidth=2.5,
        label=f"CS15 | CAGR {cs15_stats['CAGR']} | Sharpe {cs15_stats['Sharpe Ratio']}")
for (label, _), color in zip(variants, colors):
    s = results[label]
    ax.plot(navs[label].index, navs[label].values, color=color, linewidth=2.0,
            label=f"{label} | CAGR {s['CAGR']} | Sharpe {s['Sharpe Ratio']}")
ax.plot(bench_nav.index, bench_nav.values, color='#888888', linewidth=1.2,
        linestyle='--', label=f"Benchmark | CAGR {bench_cagr*100:.2f}%")

ax.set_title('MCPS15-B + Group Top 50% Shareholder Breadth Filter vs CS15', fontsize=14,
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

out_path = repo_root / "mcps15_group_filter.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f"\nSaved to: {out_path}")
plt.show()
