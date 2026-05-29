"""CS15 variation: drop industries with >75% SH decrease at 12Q lookback after RSNP."""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

REPO = Path(__file__).parent


class CS15DropHeavyDecrease(CS15Strategy):
    """CS15 + post-RSNP filter: drop industries where >75% stocks have
    decreasing shareholders at 12Q lookback."""

    def __init__(self, *args, drop_threshold=0.75, drop_lookback=12, **kwargs):
        super().__init__(*args, **kwargs)
        self.drop_threshold = drop_threshold
        self.drop_lookback = drop_lookback

    def calculate_selection(self, date: pd.Timestamp):
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max(d for d in all_dates if d <= signal_date)
        actual_lookback_start = max(d for d in all_dates
                                    if d <= (actual_signal_date - pd.DateOffset(years=1)))

        # 1. Shareholder Filters (4Q, same as CS15 baseline)
        sh_trend = self.dh.get_shareholder_trend(
            actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty:
            return {}

        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)

        # Rule 1: Group Filter (Top 50%)
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False).head(
            int(len(group_stats) * self.industry_group_top_pct))['group'].tolist()

        # Rule 2: Industry Filter (> 50%)
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries:
            return {}

        # 2. RSNP (same as CS15)
        if self.rsnp_benchmark == 'nifty_500':
            b_prices = self.dh.nifty_500_bench
        elif self.rsnp_benchmark == 'top_100':
            b_prices = self.dh.top_100_bench
        elif self.rsnp_benchmark == 'top_1000':
            b_prices = self.dh.top_1000_bench
        else:
            b_prices = getattr(self.dh, 'indices_bench', {}).get(self.rsnp_benchmark)

        if b_prices is None or b_prices.empty:
            return {}

        b_end_qs = b_prices[b_prices['date'] <= actual_signal_date]
        b_start_qs = b_prices[b_prices['date'] <= actual_lookback_start]
        if b_end_qs.empty or b_start_qs.empty:
            return {}

        bench_return = (b_end_qs['index_value'].iloc[-1] /
                        b_start_qs['index_value'].iloc[-1]) - 1

        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return (self.dh.price_df[self.dh.price_df['date'].isin(w)]
                    .sort_values('date').groupby('isin')['close'].last().to_dict())
        p1 = get_map(actual_signal_date)
        p0 = get_map(actual_lookback_start)

        industry_rsnp = []
        for ind in qualified_industries:
            isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]
            wins, total = 0, 0
            for i in isins:
                c1, c0 = p1.get(i), p0.get(i)
                if c1 and c0 and c0 > 0:
                    total += 1
                    if (c1 / c0 - 1) > bench_return:
                        wins += 1
            if total >= self.min_industry_stocks:
                industry_rsnp.append({'industry': ind, 'rsnp': wins / total})

        if not industry_rsnp:
            return {}

        ind_ranked = pd.DataFrame(industry_rsnp)
        passed_rsnp = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold].sort_values(
            'rsnp', ascending=False)
        if passed_rsnp.empty:
            return {}

        # --- NEW: 12Q heavy-decrease filter ---
        sh_trend_12q = self.dh.get_shareholder_trend(
            actual_signal_date, lookback_quarters=self.drop_lookback)
        if not sh_trend_12q.empty:
            sh_trend_12q['industry'] = sh_trend_12q['isin'].map(self.dh.isin_to_industry)
            ind_dec_12q = sh_trend_12q.groupby('industry')['decreased'].mean()
            heavy_decrease = ind_dec_12q[ind_dec_12q > self.drop_threshold].index.tolist()
            passed_rsnp = passed_rsnp[~passed_rsnp['industry'].isin(heavy_decrease)]
            if passed_rsnp.empty:
                return {}

        # 3. Universe & Liquidity
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = (liq_df.groupby('isin')['traded_val'].median()
                   .reset_index().rename(columns={'traded_val': 'med_val_21d'}))
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 4. RSI entry filter
        if not self.rsi_cache.empty:
            rsi_date = max(d for d in self.rsi_cache.index if d <= actual_signal_date)
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        # 5. Selection
        selected = []
        for ind in passed_rsnp['industry']:
            ind_stocks = (universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                          .sort_values('mc', ascending=False))
            top_stocks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_stocks:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks:
                        break
            if len(selected) >= self.num_stocks:
                break

        if not selected:
            return {}

        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}


def run_variant(dh, rdates, start_date, end_date, variant='baseline', **kwargs):
    if variant == 'drop_heavy':
        strategy = CS15DropHeavyDecrease(dh, rsnp_benchmark='nifty_500', **kwargs)
    else:
        strategy = CS15Strategy(dh, rsnp_benchmark='nifty_500')
    strategy.precompute_rsi(rdates)

    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_manager = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_manager,
                       cash_yield_rate=0.05, cash_tax_rate=0.30)
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)

    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    return nav_df, stats


def main():
    dh = DataHandler(REPO / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(REPO / "benchmarks")
    all_dates = dh.get_all_dates()

    start_date = "2019-05-15"
    end_date = "2026-05-15"

    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            if d > pd.Timestamp(end_date):
                continue
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted(set(d for d in rdates if d >= pd.Timestamp(start_date)))

    variants = {
        'CS15 baseline':            dict(variant='baseline'),
        'CS15 + drop >50% 12Q':     dict(variant='drop_heavy', drop_threshold=0.50, drop_lookback=12),
        'CS15 + drop >85% 12Q':     dict(variant='drop_heavy', drop_threshold=0.85, drop_lookback=12),
    }

    results = {}
    for label, kwargs in variants.items():
        print(f"Running {label}...")
        nav, stats = run_variant(dh, rdates, start_date, end_date, **kwargs)
        nav['date'] = pd.to_datetime(nav['date'])
        results[label] = (nav, stats)
        print(f"  -> CAGR {stats['CAGR']} | DD {stats['Max Drawdown']} | Sharpe {stats['Sharpe Ratio']}")

    # Nifty 500
    bench = dh.nifty_500_bench.copy()
    bench['date'] = pd.to_datetime(bench['date'])
    bench = bench[(bench['date'] >= pd.Timestamp(start_date)) &
                  (bench['date'] <= pd.Timestamp(end_date))]
    bench['nav'] = bench['index_value'] / bench['index_value'].iloc[0] * 10000000

    # Plot
    colors = {'CS15 baseline': '#2166ac', 'CS15 + drop >50% 12Q': '#d73027',
              'CS15 + drop >85% 12Q': '#1b7837'}
    fig, ax = plt.subplots(figsize=(14, 7))
    for label, (nav, stats) in results.items():
        ax.plot(nav['date'], nav['nav'] / 1e6, label=label, linewidth=1.8, color=colors[label])
    ax.plot(bench['date'], bench['nav'] / 1e6, label='Nifty 500', linewidth=1.5,
            color='gray', linestyle='--')

    subtitle_lines = []
    for label, (_, stats) in results.items():
        subtitle_lines.append(
            f'{label}: CAGR {stats["CAGR"]} | DD {stats["Max Drawdown"]} | Sharpe {stats["Sharpe Ratio"]}')

    ax.set_ylabel('NAV (millions)', fontsize=11)
    ax.set_title('CS15 vs CS15 + Drop Heavy SH Decrease Industries (12Q lookback)\n'
                 + '\n'.join(subtitle_lines),
                 fontsize=9.5, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('Date', fontsize=11)

    out = REPO / "outputs" / "cs15_drop_heavy_decrease.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved -> {out}")
    plt.show()


if __name__ == "__main__":
    main()
