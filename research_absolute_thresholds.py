import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class AbsoluteThresholdStrategy(ContrarianBreadthStrategy):
    """Overrides calculate_selection to support absolute group thresholds."""
    def __init__(self, *args, group_absolute_threshold=0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_absolute_threshold = group_absolute_threshold

    def calculate_selection(self, date: pd.Timestamp) -> pd.Series:
        # Replicate part of calculate_selection but change group filter to absolute
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liquidity_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        if universe.empty: return {}
        
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # (i) ABSOLUTE Industry Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        top_groups = group_stats[group_stats['mean'] >= self.group_absolute_threshold]['group'].tolist()
        if not top_groups: return {}
        
        # (ii) Industry Filter (Same as official)
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # Breadth (RSNP) & RSI Filters (Reused from base for consistency)
        # We need to compute bench return and price maps
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

        # RSI Entry
        rsi_lookup_date = max([d for d in self.rsi_cache.index if d <= actual_calc_date])
        univ_isins = universe['isin'].tolist()
        valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
        rsis = self.rsi_cache.loc[rsi_lookup_date, valid_isins]
        passed_isins = rsis[rsis > self.rsi_threshold].index.tolist()
        universe = universe[universe['isin'].isin(passed_isins)]

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
        w = 1.0 / len(selected_isins)
        return {isin: w for isin in selected_isins}

def run_threshold_research():
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

    results = {}
    
    # 1. Baseline
    print("\nRunning Official (Relative 50% Group / Absolute 50% Ind)...")
    strat0 = ContrarianBreadthStrategy(dh, num_stocks=15)
    port0 = Portfolio(10000000)
    eng0 = SimEngine(dh, port0, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng0.run(start_date, end_date, strat0.calculate_selection, rebalance_dates, verbose=False)
    results["Official (Rel 50/Abs 50)"] = calculate_metrics(pd.DataFrame(port0.nav_history))

    # 2. Both 50% Absolute
    print("\nRunning Both 50% Absolute...")
    strat1 = AbsoluteThresholdStrategy(dh, num_stocks=15, group_absolute_threshold=0.5)
    port1 = Portfolio(10000000)
    eng1 = SimEngine(dh, port1, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng1.run(start_date, end_date, strat1.calculate_selection, rebalance_dates, verbose=False)
    results["Both 50% Absolute"] = calculate_metrics(pd.DataFrame(port1.nav_history))

    # 3. 70% Group / 50% Industry Absolute
    print("\nRunning 70% Group / 50% Industry Absolute...")
    strat2 = AbsoluteThresholdStrategy(dh, num_stocks=15, group_absolute_threshold=0.7)
    port2 = Portfolio(10000000)
    eng2 = SimEngine(dh, port2, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng2.run(start_date, end_date, strat2.calculate_selection, rebalance_dates, verbose=False)
    results["70% Gr / 50% Ind Abs"] = calculate_metrics(pd.DataFrame(port2.nav_history))

    # 4. 30% Group / 50% Industry Absolute
    print("\nRunning 30% Group / 50% Industry Absolute...")
    strat3 = AbsoluteThresholdStrategy(dh, num_stocks=15, group_absolute_threshold=0.3)
    port3 = Portfolio(10000000)
    eng3 = SimEngine(dh, port3, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng3.run(start_date, end_date, strat3.calculate_selection, rebalance_dates, verbose=False)
    results["30% Gr / 50% Ind Abs"] = calculate_metrics(pd.DataFrame(port3.nav_history))

    print("\n" + "="*125)
    print("COMPARISON: RELATIVE vs ABSOLUTE SHAREHOLDER THRESHOLDS")
    print("="*125)
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = list(results.keys())
    print(f"{'Metric':<20} | {headers[0]:>25} | {headers[1]:>25} | {headers[2]:>25} | {headers[3]:>20}")
    print("-" * 125)
    for m in metrics:
        print(f"{m:<20} | {results[headers[0]][m]} | {results[headers[1]][m]} | {results[headers[2]][m]} | {results[headers[3]][m]}")
    print("="*125)

if __name__ == "__main__":
    run_threshold_research()
