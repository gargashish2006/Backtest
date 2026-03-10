
import pandas as pd
from typing import Dict, List, Optional
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from engine.portfolio import Portfolio

class IndustryQualificationStrategy(ContrarianBreadthStrategy):
    """
    Semi-Static Strategy:
    1. Maintenance: Keep stocks if their Industry still passes Champion filters.
    2. Replacement: Fill empty slots with stocks from NEW Industries only.
    3. Allocation: 
       - 'rebalance': Equal weight all holdings.
       - 'cash': Keep existing weights for held stocks, allocate new cash to new stocks.
    """
    def __init__(self, data_handler, 
                 portfolio: Portfolio,
                 allocation_mode: str = 'rebalance',  # 'rebalance' | 'cash'
                 **kwargs):
        super().__init__(data_handler, **kwargs)
        self.portfolio = portfolio
        self.allocation_mode = allocation_mode
        self.kept_isins = [] 
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # Implementation of "Industry Qualification" Logic
        
        # 1. DATA PREP (Same as Standard Champion)
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        # Universe
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

        # Shareholder Data
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # --- QUALIFICATION CHECK LOGIC ---
        
        # We need to determine which Industries are "Qualified" RIGHT NOW.
        # This mirrors the Entry Logic filters.
        
        # 1. Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        # 2. Industry Filter
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        
        # 3. RSNP Filter
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
        
        final_qualified_industries = []
        industry_rsnp_scores = {}
        
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins = 0; eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            
            score = wins/eligible if eligible > 0 else 0
            if score >= self.rsnp_threshold:
                final_qualified_industries.append(ind)
                industry_rsnp_scores[ind] = score
                
        # Sorted list of best industries for new picks
        ranked_industries = sorted(final_qualified_industries, key=lambda x: industry_rsnp_scores[x], reverse=True)
        
        # --- MAINTENANCE STEP: Check Existing Holdings ---
        current_holdings = list(self.portfolio.holdings.keys())
        kept_isins = []
        held_industries = set()
        
        for isin in current_holdings:
            # What is this stock's industry?
            ind = self.dh.isin_to_industry.get(isin)
            
            if ind and ind in final_qualified_industries:
                # KEEP!
                kept_isins.append(isin)
                held_industries.add(ind)
            else:
                # SELL (Implicitly, by not adding to kept_isins)
                pass
                
        # --- REPLACEMENT STEP: Fill Empty Slots ---
        slots_needed = self.num_stocks - len(kept_isins)
        new_picks = []
        
        if slots_needed > 0:
            for ind in ranked_industries:
                if len(new_picks) >= slots_needed: break
                
                # CONSTRAINT: New Industry Only
                if ind in held_industries:
                    continue
                    
                ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                ind_universe = ind_universe.sort_values('mc', ascending=False)
                top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
                
                for isin in top_for_ind:
                    # Don't buy what we already own (redundant check but safe)
                    if isin not in kept_isins and isin not in new_picks:
                        new_picks.append(isin)
                        if len(new_picks) >= slots_needed: break
                        
        final_list = kept_isins + new_picks
        if not final_list: return {}
        
        # --- ALLOCATION STEP ---
        target_weights = {}
        
        if self.allocation_mode == 'rebalance':
            # Variation 1: Equal Weight Everything
            w = 1.0 / len(final_list)
            target_weights = {isin: w for isin in final_list}
            
        elif self.allocation_mode == 'cash':
            # Variation 2: Drift Kept, Cash to New
            prices = self.dh.get_daily_prices(date)
            total_val = self.portfolio.get_market_value(prices)
            cash = self.portfolio.cash
            total_nav = total_val + cash
            investable_nav = total_nav * 0.98 # Safety buffer used in SimEngine
            
            # 1. Calculate weights for KEPT stocks to maintain current qty
            # We want TargetValue ~= CurrentValue
            # W = CurrentVal / InvestableNAV
            
            used_weight = 0.0
            for isin in kept_isins:
                qty = sum(lot.remaining_qty for lot in self.portfolio.holdings[isin])
                price = prices.get(isin, 0)
                curr_val = qty * price
                
                w = curr_val / investable_nav if investable_nav > 0 else 0
                target_weights[isin] = w
                used_weight += w
                
            # 2. Allocate Remaining Weight to NEW stocks
            remaining_weight = max(0, 1.0 - used_weight)
            num_new = len(new_picks)
            
            if num_new > 0:
                w_new = remaining_weight / num_new
                for isin in new_picks:
                    target_weights[isin] = w_new
            else:
                # If no new stocks, maybe re-distribute excess cash?
                # For 'cash' mode, usually we just let it sit or add to existing?
                # User said: "3 new stocks equally weighted with the amount in cash + amount we got by selling 3"
                # This implies fully investing the available capital.
                # Our logic above (remaining_weight / num_new) implicitly does this.
                pass
                
        return target_weights
