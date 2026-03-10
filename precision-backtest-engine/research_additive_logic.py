import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class AdditiveContrarianStrategy(ContrarianBreadthStrategy):
    """Overrides calculate_selection to use Additive (Sum >= 1.0) shareholder filtering."""
    def calculate_selection(self, date: pd.Timestamp) -> pd.Series:
        # 1. Setup Dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])

        # 2. Universe & Liquidity (Reused from base)
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liquidity_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 3. Additive Shareholder Filter
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)

        # Calculate Group Means
        group_means = sh_trend.groupby('group')['decreased'].mean().to_dict()
        
        # Calculate Industry Stats
        ind_stats = sh_trend.groupby(['group', 'industry'])['decreased'].agg(['mean', 'count']).reset_index()
        
        # NEW LOGIC: Sum >= 1.0
        ind_stats['group_score'] = ind_stats['group'].map(group_means)
        ind_stats['combined_score'] = ind_stats['group_score'] + ind_stats['mean']
        
        qualified_industries = ind_stats[ind_stats['combined_score'] >= 1.0]['industry'].tolist()
        if not qualified_industries: return {}

        # 4. RSNP Ranking (Reused from base)
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1

        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-30:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)

        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins, eligible = 0, 0
            for isin in ind_isins:
                p1, p0 = p_end_map.get(isin), p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})

        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)

        # 5. RSI Entry
        rsi_lookup_date = max([d for d in self.rsi_cache.index if d <= actual_calc_date])
        univ_isins = universe['isin'].tolist()
        valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
        rsis = self.rsi_cache.loc[rsi_lookup_date, valid_isins]
        passed_isins = rsis[rsis > self.rsi_threshold].index.tolist()
        universe = universe[universe['isin'].isin(passed_isins)]

        # 6. Final Selection
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
            ind_universe = ind_universe.sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
        
        if not selected_isins: return {}
        num_final = len(selected_isins)
        w = 1.0 / num_final if num_final >= self.num_stocks else min(0.10, max(0.0667, 1.0/num_final))
        return {isin: w for isin in selected_isins}

def run_additive_research():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date, end_date = "2017-05-15", "2026-02-05"
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date): rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    # 1. Run Official
    print("\nRunning Official Strategy...")
    strat_off = ContrarianBreadthStrategy(dh, num_stocks=15)
    port_off = Portfolio(10000000)
    eng_off = SimEngine(dh, port_off, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng_off.run(start_date, end_date, strat_off.calculate_selection, rebalance_dates, verbose=False)
    res_off = calculate_metrics(pd.DataFrame(port_off.nav_history))

    # 2. Run Additive
    print("\nRunning Additive (Sum >= 100%) Strategy...")
    strat_add = AdditiveContrarianStrategy(dh, num_stocks=15)
    port_add = Portfolio(10000000)
    eng_add = SimEngine(dh, port_add, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng_add.run(start_date, end_date, strat_add.calculate_selection, rebalance_dates, verbose=False)
    res_add = calculate_metrics(pd.DataFrame(port_add.nav_history))

    print("\n" + "="*80)
    print("COMPARISON: OFFICIAL vs ADDITIVE (Sum >= 100%)")
    print("="*80)
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    print(f"{'Metric':<20} | {'Official (50/50)':>25} | {'Additive (Sum >= 100%)':>25}")
    print("-" * 80)
    for m in metrics:
        print(f"{m:<20} | {res_off[m]:>25} | {res_add[m]:>25}")
    print("="*80)

if __name__ == "__main__":
    run_additive_research()
