
import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class GroupRSNPStrategy:
    """
    Variation of Contrarian Breadth Strategy where RSNP (Breadth) is calculated 
    at the INDUSTRY GROUP level, and Industries are ranked by their Group's score.
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
                  month_low_exit: bool = False): 
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.rsnp_threshold = rsnp_threshold
        self.rsnp_exit_threshold = rsnp_exit_threshold
        self.rsi_threshold = rsi_threshold
        self.rsi_exit_threshold = rsi_exit_threshold
        self.weekly_low_exit = weekly_low_exit
        self.month_low_exit = month_low_exit
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        self.min_industry_size = min_industry_size
        self.price_lookback_days = 30
        
        # Pre-compute Caches
        if self.rsi_threshold > 0 or self.rsi_exit_threshold:
            self.rsi_cache = self.dh.get_weekly_rsi_cache()
        else:
            self.rsi_cache = pd.DataFrame()
            
        if self.weekly_low_exit:
            self.low_3_cache = self.dh.get_weekly_low_3_cache()
        else:
            self.low_3_cache = pd.DataFrame()

        if self.month_low_exit:
            self.month_low_cache = self.dh.get_prev_month_low_cache()
        else:
            self.month_low_cache = pd.DataFrame()
        
    def check_exits(self, date: pd.Timestamp, current_portfolio_isins: List[str]) -> List[str]:
        # Reuse same exit logic as Champion
        if not current_portfolio_isins: return []
        exit_list = []
        
        lookup_date = date - pd.Timedelta(days=1)
        prices = self.dh.get_daily_prices(date)
        
        def get_best_date(index, target):
            if target < index[0]: return None
            idx = index.searchsorted(target, side='right')
            return index[idx-1] if idx > 0 else None

        if self.rsi_exit_threshold and not self.rsi_cache.empty:
            actual_lookup = get_best_date(self.rsi_cache.index, lookup_date)
            if actual_lookup:
                valid_isins = [i for i in current_portfolio_isins if i in self.rsi_cache.columns]
                if valid_isins:
                    current_rsis = self.rsi_cache.loc[actual_lookup, valid_isins]
                    rsi_exits = current_rsis[current_rsis < self.rsi_exit_threshold].index.tolist()
                    exit_list.extend(rsi_exits)
                    
        if self.weekly_low_exit and not self.low_3_cache.empty:
            actual_lookup = get_best_date(self.low_3_cache.index, lookup_date)
            if actual_lookup:
                valid_isins = [i for i in current_portfolio_isins if i in self.low_3_cache.columns]
                for isin in valid_isins:
                    floor = self.low_3_cache.loc[actual_lookup, isin]
                    current_p = prices.get(isin, 0)
                    if current_p > 0 and current_p <= floor:
                        if isin not in exit_list:
                            exit_list.append(isin)

        if self.month_low_exit and not self.month_low_cache.empty:
            actual_lookup = get_best_date(self.month_low_cache.index, lookup_date)
            if actual_lookup:
                valid_isins = [i for i in current_portfolio_isins if i in self.month_low_cache.columns]
                for isin in valid_isins:
                    floor = self.month_low_cache.loc[actual_lookup, isin]
                    current_p = prices.get(isin, 0)
                    if current_p > 0 and current_p <= floor:
                        if isin not in exit_list:
                            exit_list.append(isin)
                    
        return list(set(exit_list))

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Calculation dates (1 week prior to rebalance)
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
        
        # 3. Shareholder Filter (Two-Tier)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        if self.min_industry_size > 0:
            ind_counts = sh_trend['industry'].value_counts()
            valid_inds = ind_counts[ind_counts >= self.min_industry_size].index
            sh_trend = sh_trend[sh_trend['industry'].isin(valid_inds)]
            
        if sh_trend.empty: return {}
        
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
        
        # 4. RSNP Ranking (GROUP LEVEL)
        # Benchmark Return
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
        
        # MODIFIED: Calculate RSNP for GROUPS, assign to Industries
        # First, find all groups for our qualified industries
        # (We use a set to avoid recalculating for same group multiple times)
        relevant_groups = set()
        ind_to_group = {}
        
        # Map industries to groups
        for ind in qualified_industries:
            # Find ANY stock in this industry and get its group (inefficient but works if map is stock-level)
            # Better: iterate dh.isin_to_industry and match
            # Actually, we have sh_trend df which has 'industry' and 'group' columns!
            # Let's use that map
            group_name = sh_trend[sh_trend['industry'] == ind]['group'].iloc[0]
            ind_to_group[ind] = group_name
            relevant_groups.add(group_name)
            
        # Calculate RSNP Score for each relevant GROUP
        group_rsnp_scores = {}
        
        for grp in relevant_groups:
            # Find all stocks in this GROUP (using dh map)
            grp_isins = [isin for isin, name in self.dh.isin_to_group.items() if name == grp]
            
            wins = 0
            eligible = 0
            for isin in grp_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            
            score = wins / eligible if eligible > 0 else 0
            group_rsnp_scores[grp] = score
            
        # Assign Scores to Industries
        industry_rsnp = []
        for ind in qualified_industries:
            grp = ind_to_group[ind]
            score = group_rsnp_scores.get(grp, 0)
            industry_rsnp.append({'industry': ind, 'rsnp': score}) # Scoring by GROUP RSNP
            
        if not industry_rsnp: return {}
        
        ind_ranked = pd.DataFrame(industry_rsnp)
        
        # Optional: Secondary sort by Industry RSNP? (Not implemented based on prompt "rank based on that")
        
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
        if num_final >= self.num_stocks:
            w = 1.0 / num_final
        else:
            w = max(0.0667, 1.0 / num_final) if num_final > 0 else 0
            w = min(0.10, w)
            
        return {isin: w for isin in selected_isins}
