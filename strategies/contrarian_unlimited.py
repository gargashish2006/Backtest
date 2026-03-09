import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class ContrarianUnlimitedStrategy:
    """
    Unlimited Variant of the Contrarian Breadth Strategy:
    1. No limit on total stocks (num_stocks ignored).
    2. No limit on stocks per industry (max_per_industry ignored).
    3. All stocks passing the RSNP 0.40 hurdle are selected.
    4. Equal weighting across all selected stocks.
    """
    def __init__(self, data_handler: DataHandler,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 rsnp_threshold: float = 0.40): 
        self.dh = data_handler
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.rsnp_threshold = rsnp_threshold
        self.price_lookback_days = 30

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
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
        
        if len(liquidity_window) < 10:
             avg_liq = universe[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        if universe.empty: return {}
        
        sh_trend = self.dh.get_shareholder_trend(date)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        b_end = self.dh.top_1000_bench[self.dh.top_1000_bench['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = self.dh.top_1000_bench[self.dh.top_1000_bench['date'] <= actual_lookback_start]['index_value'].iloc[-1]
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
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
                
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        
        # 5. UNLIMITED Stock Selection
        selected_isins = []
        for ind in ind_ranked['industry']:
            # Take ALL qualifying stocks in the industry from our market universe
            ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
            selected_isins.extend(ind_universe['isin'].tolist())
            
        if not selected_isins: return {}
        
        # Unique list and equal weight
        selected_isins = list(set(selected_isins))
        w = 1.0 / len(selected_isins)
        return {isin: w for isin in selected_isins}
