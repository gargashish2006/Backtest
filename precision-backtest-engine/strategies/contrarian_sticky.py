import pandas as pd
from typing import Dict, List, Optional, Set
from data.data_handler import DataHandler

class ContrarianStickyStrategy:
    """
    Implements a 'Sticky' version of the Champion Strategy:
    1. Holds existing stocks if they still meet basic criteria:
       - Must be in the Top 1000/Liquid universe.
       - Their Industry must be in the 'Qualified' list (Group+Ind+RSNP filters).
    2. Fills remaining slots using the standard ranking logic (Highest RSNP industries).
    3. Rebalances Quarterly (or as defined by caller).
    """
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 rsnp_threshold: float = 0.40): 
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.rsnp_threshold = rsnp_threshold
        self.price_lookback_days = 30
        
        # State Tracking
        self.held_isins: Set[str] = set()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns target weights for the portfolio."""
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # -------------------------------------------------------------
        # 1. DEFINE UNIVERSE & FILTERS (Same as Champion)
        # -------------------------------------------------------------
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        # Top 1000 by Market Cap
        universe_df = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liquidity_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        
        if len(liquidity_window) < 10:
             avg_liq = universe_df[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        
        universe_df = pd.merge(universe_df, avg_liq, on='isin', how='left')
        universe_df = universe_df[universe_df['avg_val_21d'] > (universe_df['mc'] * self.liquidity_threshold_pct)]
        
        current_universe_isins = set(universe_df['isin'].tolist())
        
        # Shareholder Filters
        sh_trend = self.dh.get_shareholder_trend(date)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        
        qualified_industries = [] # List of industry names that pass all filters
        
        if not group_stats.empty:
            num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
            top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
            
            ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
            ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
            # Industry Filter
            candidates = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
            
            # RSNP Filter
            if candidates:
                b_end_val = self.dh.top_1000_bench[self.dh.top_1000_bench['date'] <= actual_calc_date]['index_value'].iloc[-1]
                b_start_val = self.dh.top_1000_bench[self.dh.top_1000_bench['date'] <= actual_lookback_start]['index_value'].iloc[-1]
                bench_ret = (b_end_val / b_start_val) - 1
                
                # Pre-fetch prices
                window_dates = [d for d in all_dates if d <= actual_calc_date][-self.price_lookback_days:]
                sub = self.dh.price_df[self.dh.price_df['date'].isin(window_dates)]
                p_end_map = sub.sort_values('date').groupby('isin')['close'].last().to_dict()
                
                # Start window
                start_win = [d for d in all_dates if d <= actual_lookback_start][-self.price_lookback_days:]
                sub_start = self.dh.price_df[self.dh.price_df['date'].isin(start_win)]
                p_start_map = sub_start.sort_values('date').groupby('isin')['close'].last().to_dict()
                
                industry_rsnp_scores = []
                for ind in candidates:
                    ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
                    wins, eligible = 0, 0
                    for x in ind_isins:
                        p1 = p_end_map.get(x)
                        p0 = p_start_map.get(x)
                        if p1 and p0 and p0 > 0:
                            eligible += 1
                            if (p1/p0 - 1) > bench_ret:
                                wins += 1
                    rsnp = wins/eligible if eligible > 0 else 0
                    if rsnp >= self.rsnp_threshold:
                         industry_rsnp_scores.append({'industry': ind, 'rsnp': rsnp})
                         
                qualified_industries = [x['industry'] for x in industry_rsnp_scores]
                # Keep sorted dataframe for new selection
                ind_ranked_df = pd.DataFrame(industry_rsnp_scores).sort_values('rsnp', ascending=False)
            else:
                ind_ranked_df = pd.DataFrame()
        else:
            ind_ranked_df = pd.DataFrame()
            
        qualified_industries_set = set(qualified_industries)
        
        # -------------------------------------------------------------
        # 2. APPLY STICKY LOGIC
        # -------------------------------------------------------------
        kept_portfolio = []
        
        # Current Holdings Check
        for isin in self.held_isins:
            # Check 1: Must be in current universe (Top 1000 + Liq)
            if isin not in current_universe_isins:
                continue
                
            # Check 2: Industry must be in the 'Qualified' list
            ind = self.dh.isin_to_industry.get(isin)
            if ind not in qualified_industries_set:
                continue
                
            # Keep stock
            kept_portfolio.append(isin)
            
        # -------------------------------------------------------------
        # 3. FILL VACANCIES
        # -------------------------------------------------------------
        slots_needed = self.num_stocks - len(kept_portfolio)
        
        if slots_needed > 0 and not ind_ranked_df.empty:
            # Count current industry allocation in kept portfolio
            ind_counts = {}
            for item in kept_portfolio:
                i_name = self.dh.isin_to_industry.get(item)
                ind_counts[i_name] = ind_counts.get(i_name, 0) + 1
            
            # Fill from ranked industries
            for target_ind in ind_ranked_df['industry']:
                if slots_needed <= 0: break
                
                current_count = ind_counts.get(target_ind, 0)
                if current_count >= self.max_per_industry:
                    continue
                
                # Get eligible stocks for this industry
                candidates = universe_df[universe_df['isin'].map(self.dh.isin_to_industry) == target_ind]
                candidates = candidates.sort_values('mc', ascending=False)['isin'].tolist()
                
                for cand in candidates:
                    if cand not in kept_portfolio:
                        kept_portfolio.append(cand)
                        current_count += 1
                        slots_needed -= 1
                        
                        if current_count >= self.max_per_industry:
                            break
                        if slots_needed <= 0:
                            break
                
                ind_counts[target_ind] = current_count
                
        # -------------------------------------------------------------
        # 4. FINALIZE & WEIGHT
        # -------------------------------------------------------------
        self.held_isins = set(kept_portfolio)
        
        if not kept_portfolio: 
            return {}
            
        num_final = len(kept_portfolio)
        
        # Equal Weighting
        if num_final >= self.num_stocks:
            w = 1.0 / num_final
        else:
            w = max(0.0667, 1.0 / num_final)
            w = min(0.10, w)
            
        return {isin: w for isin in kept_portfolio}
