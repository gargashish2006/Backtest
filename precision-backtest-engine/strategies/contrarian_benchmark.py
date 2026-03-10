import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class ContrarianBenchmarkStrategy:
    """
    Variant strategy ranking industries by Benchmark returns instead of RSNP.
    Steps:
    1. Filter Universe (Top 1000 MC + Liquidity).
    2. Group-level Shareholder Filter (Top 40%).
    3. Industry-level Shareholder Filter (>= 60%).
    4. Rank qualified industries by 1-year Benchmark Return.
    5. Select top 15 stocks (Max 3/industry, highest MC).
    """
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.40,
                 industry_decrease_min_pct: float = 0.60):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns target weights for the portfolio based on Benchmark Ranking."""
        # 1. Calculation dates (1 week prior)
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # 2. Market Universe & Liquidity Filtering
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
        # Liquidity Filter
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liquidity_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        
        if len(liquidity_window) < 10:
             avg_liq = universe[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        if universe.empty: return {}
        
        # 3. Shareholder Filter (Identical to RSNP version)
        sh_trend = self.dh.get_shareholder_trend(date)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # Group Level (Top 40%)
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        top_groups = group_stats.sort_values('mean', ascending=False).head(max(1, int(len(group_stats)*self.industry_group_top_pct)))['group'].tolist()
        
        # Industry Level (60% Decrease)
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 4. Industry Ranking by BENCHMARK RETURN
        industry_bench_returns = []
        for ind in qualified_industries:
            p_end = self.dh.get_industry_benchmark_price(ind, actual_calc_date)
            p_start = self.dh.get_industry_benchmark_price(ind, actual_lookback_start)
            if p_end > 0 and p_start > 0:
                ret = (p_end / p_start) - 1
                industry_bench_returns.append({'industry': ind, 'bench_return': ret})
        
        if not industry_bench_returns: return {}
        ind_ranked = pd.DataFrame(industry_bench_returns).sort_values('bench_return', ascending=False)
        
        # 5. Stock Selection (same logic)
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
        
        # 6. Weighting
        w = 1.0 / len(selected_isins) if len(selected_isins) >= 15 else 0.10
        return {isin: w for isin in selected_isins}
