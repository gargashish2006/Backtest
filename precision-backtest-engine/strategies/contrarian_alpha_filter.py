
import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

class ContrarianAlphaFilterStrategy(ContrarianBreadthStrategy):
    """
    Subclass of ContrarianBreadthStrategy that adds an individual stock alpha filter.
    Only stocks outperforming the benchmark over the last 1 year are selected.
    """
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 rsnp_threshold: float = 0.40,
                 shareholder_lookback_quarters: int = 4,
                 min_industry_size: int = 0,
                 rsnp_exit_threshold: float = None,
                 rsi_threshold: float = 40,
                 rsi_exit_threshold: float = 39,
                 weekly_low_exit: bool = False,
                 month_low_exit: bool = False,
                 stock_alpha_filter: bool = True):
        
        super().__init__(data_handler, num_stocks, max_per_industry, universe_size,
                         liquidity_threshold_pct, industry_group_top_pct, 
                         industry_decrease_min_pct, rsnp_threshold, 
                         shareholder_lookback_quarters, min_industry_size,
                         rsnp_exit_threshold, rsi_threshold, rsi_exit_threshold,
                         weekly_low_exit, month_low_exit)
        self.stock_alpha_filter = stock_alpha_filter

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """
        Overrides calculate_selection to add the individual stock alpha filter.
        """
        # 1-4. Run the original industry-level selection logic by calling super
        # However, because we need to inject the filter BEFORE stock selection but AFTER industry ranking,
        # and base class doesn't have hooks, we have to borrow the logic.
        
        # NOTE: For research velocity, we are duplicating parts of the logic here 
        # to ensure the Point-to-Point Alpha Filter is applied correctly.
        
        # Re-using the logic from the base class but adding the stock-level check.
        
        # 1. Calculation dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # 2. Market Universe & Liquidity Filtering
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
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
        
        # 3. Shareholder Filter (Point-to-Point)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # (i) Industry Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        # (ii) Industry Filter
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 4. RSNP Ranking
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-self.price_lookback_days:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
        
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 5. RSI Entry Filter
        if self.rsi_threshold > 0 and not self.rsi_cache.empty:
             valid_cache_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
             if valid_cache_dates:
                 rsi_lookup_date = max(valid_cache_dates)
                 univ_isins = universe['isin'].tolist()
                 valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
                 if valid_isins:
                     rsis = self.rsi_cache.loc[rsi_lookup_date, valid_isins]
                     passed_isins = rsis[rsis > self.rsi_threshold].index.tolist()
                     universe = universe[universe['isin'].isin(passed_isins)]
        
        # 5.5 NEW: Stock-Level Alpha Filter
        if self.stock_alpha_filter:
            alpha_isins = []
            for isin in universe['isin']:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 is not None and p0 is not None and p0 > 0:
                    if (p1/p0 - 1) > bench_return:
                        alpha_isins.append(isin)
            universe = universe[universe['isin'].isin(alpha_isins)]
        
        if universe.empty: return {}

        # 6. Stock Selection
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
        
        # 7. Weighting
        num_final = len(selected_isins)
        w = 1.0 / num_final if num_final >= self.num_stocks else min(0.10, max(0.0667, 1.0 / num_final))
        return {isin: w for isin in selected_isins}
