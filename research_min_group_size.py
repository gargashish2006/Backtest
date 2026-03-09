
import pandas as pd
from pathlib import Path
from typing import Dict, List
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class MinGroupSizeStrategy(ContrarianBreadthStrategy):
    """
    Variation of Champion Strategy that ignores industry groups 
    with fewer than 5 stocks in the database.
    """
    def __init__(self, data_handler, min_group_stocks: int = 5, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.min_group_stocks = min_group_stocks

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # Reuse most of the base logic but inject the group filter
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.DateOffset(years=1))])
        
        # 1. Universe
        universe = self.dh.get_universe(actual_calc_date, size=self.universe_size)
        if universe.empty: return {}
        
        # 2. Liquidity Filter
        liquidity_window = [d for d in all_dates if d <= date][-21:]
        if len(liquidity_window) < 10:
             avg_liq = universe[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        if universe.empty: return {}

        # 3. Shareholder Filter
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # --- NEW FILTER: Minimum Group Size ---
        group_counts = sh_trend.groupby('group')['isin'].count().reset_index().rename(columns={'isin': 'stock_count'})
        valid_groups = group_counts[group_counts['stock_count'] >= self.min_group_stocks]['group'].tolist()
        sh_trend = sh_trend[sh_trend['group'].isin(valid_groups)]
        # --------------------------------------

        if sh_trend.empty: return {}
        
        # A. Industry Group Filter (Top X%)
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        group_stats = group_stats.sort_values('decreased', ascending=False)
        top_n = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.head(top_n)['group'].tolist()
        
        # B. Industry Breadth Filter (Min X%)
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 4. RSNP Ranking
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()
        p1 = get_map(actual_calc_date)
        p0 = get_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]
            wins, total = 0, 0
            for i in isins:
                c1, c0 = p1.get(i), p0.get(i)
                if c1 and c0 and c0 > 0:
                    total += 1
                    if (c1/c0 - 1) > bench_return: wins += 1
            if total > 0: industry_rsnp.append({'industry': ind, 'rsnp': wins/total})
            
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 5. RSI Entry
        if not self.rsi_cache.empty:
             rsi_date = max([d for d in self.rsi_cache.index if d <= actual_calc_date])
             passed_isins = [i for i in universe['isin'] if self.rsi_cache.loc[rsi_date].get(i, 0) > self.rsi_threshold]
             universe = universe[universe['isin'].isin(passed_isins)]
        if universe.empty: return {}

        # 6. Selection
        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_3 = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_3:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break
            
        if not selected: return {}
        w = 1.0 / len(selected)
        return {isin: w for isin in selected}

def run_min_group_research():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)])

    print("Running Champion with Min Group Size = 5...")
    strategy = MinGroupSizeStrategy(dh, min_group_stocks=5)
    strategy.precompute_rsi(rdates)
    
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax)
    
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(portfolio.nav_history))
    print("\n" + "="*40)
    print("MIN GROUP SIZE (N=5) PERFORMANCE")
    print("="*40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*40)

if __name__ == "__main__":
    run_min_group_research()
