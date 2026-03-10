"""
TEST: CS15 Median vs Average Liquidity Filter
Does NOT modify cs15_strategy.py. Uses a local subclass override.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics


class CS15MedianLiquidity(CS15Strategy):
    """CS15 variant: uses MEDIAN traded value (not mean) for the 21-day liquidity filter."""

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Identical to CS15Strategy.calculate_selection but uses median for liquidity."""
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_signal_date - pd.DateOffset(years=1))])

        # 1. Shareholder Filters
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}

        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)

        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False).head(
            int(len(group_stats) * self.industry_group_top_pct))['group'].tolist()

        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}

        # 2. RSNP Momentum
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_signal_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1

        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()

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
                    if (c1 / c0 - 1) > bench_return: wins += 1
            if total > 0: industry_rsnp.append({'industry': ind, 'rsnp': wins / total})

        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        passed_rsnp = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold].sort_values('rsnp', ascending=False)
        if passed_rsnp.empty: return {}

        # 3. Universe & Liquidity — *** MEDIAN instead of MEAN ***
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        # KEY CHANGE: .median() instead of .mean()
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 4. RSI Entry Filter
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty: return {}

        # 5. Selection
        selected = []
        for ind in passed_rsnp['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_stocks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_stocks:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break

        if not selected: return {}

        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}


def run():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-02-05"
    all_dates = dh.get_all_dates()
    rdates = sorted([
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2017, 2027) for m in [2, 5, 8, 11]
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ])
    rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

    fee_model = FeeModel(0.0015, 0.005)

    # --- CS15 Original (Average Liquidity) ---
    print("\nRunning CS15 (Average Liquidity — original)...")
    p1 = Portfolio(10000000)
    s1 = CS15Strategy(dh)
    s1.precompute_rsi(rdates)
    e1 = SimEngine(dh, p1, fee_model, TaxManager(0.20, 0.125), cash_yield_rate=0.05, cash_tax_rate=0.30)
    e1.run(start_date, end_date, s1.calculate_selection, rdates, verbose=False)
    stats1 = calculate_metrics(pd.DataFrame(p1.nav_history))

    # --- CS15 Median Liquidity (Test) ---
    print("Running CS15 (Median Liquidity — test)...")
    p2 = Portfolio(10000000)
    s2 = CS15MedianLiquidity(dh)
    s2.precompute_rsi(rdates)
    e2 = SimEngine(dh, p2, fee_model, TaxManager(0.20, 0.125), cash_yield_rate=0.05, cash_tax_rate=0.30)
    e2.run(start_date, end_date, s2.calculate_selection, rdates, verbose=False)
    stats2 = calculate_metrics(pd.DataFrame(p2.nav_history))

    print("\n" + "=" * 65)
    print(f"{'Metric':<25} | {'CS15 (Average Liq)':<20} | {'CS15 (Median Liq)':<20}")
    print("-" * 65)
    for k in stats1.keys():
        print(f"{k:<25} | {stats1[k]:<20} | {stats2.get(k, 'N/A'):<20}")
    print("=" * 65)


if __name__ == "__main__":
    run()
