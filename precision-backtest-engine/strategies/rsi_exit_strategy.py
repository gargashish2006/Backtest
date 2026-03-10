
import pandas as pd
from typing import Dict, List, Optional
from strategies.contrarian_breadth import ContrarianBreadthStrategy

class RSIExitStrategy(ContrarianBreadthStrategy):
    """
    RSI Exit Strategy (Momentum Hold):
    1. Maintenance: Keep stocks if Weekly RSI >= 39. Else Sell.
    2. Replacement: Fill empty slots with Champion stocks from NEW Industries only.
    3. Allocation: Full Rebalance (Equal Weight).
    """
    def __init__(self, data_handler, **kwargs):
        # Allow passing rsi_threshold for entry (default 40 in base)
        # We explicitly set exit_threshold=39 for clarity, though used manually here.
        super().__init__(data_handler, **kwargs)
        self.kept_isins = [] 
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # Implementation of RSI Exit Logic
        
        # 1. Standard Champion Logic for CANDIDATE GENERATION
        # We need the full ranked list of industries/stocks.
        # Copy-pasting core logic for transparency & control.
        
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
        
        # Filters
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # RSNP Ranking
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
            wins = 0; eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if eligible > 0: industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
                
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0: ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # Apply RSI Entry Filter to Universe (RSI > 40)
        # This ensures NEW stocks have momentum.
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
        
        # --- STATEFUL LOGIC: MAINTENANCE ---
        
        current_holdings = list(self.kept_isins)
        self.kept_isins = []
        held_industries = set()
        
        # Check RSI for existing holdings
        if not self.rsi_cache.empty:
            valid_cache_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
            if valid_cache_dates:
                 rsi_lookup_date = max(valid_cache_dates)
                 # Get RSI for all holdings
                 valid_h = [h for h in current_holdings if h in self.rsi_cache.columns]
                 if valid_h:
                     h_rsis = self.rsi_cache.loc[rsi_lookup_date, valid_h]
                     
                     for isin in current_holdings:
                         keep = False
                         if isin in h_rsis.index:
                             rsi_val = h_rsis[isin]
                             # CHECK: RSI >= 39?
                             if rsi_val >= 39: # Hardcoded rule as per user request
                                 keep = True
                         else:
                             # No RSI data? Sell or Keep? 
                             # Assume sell if no data to verify momentum.
                             pass
                             
                         if keep:
                             self.kept_isins.append(isin)
                             ind = self.dh.isin_to_industry.get(isin)
                             if ind: held_industries.add(ind)
                             
        # If caching failed entirely, maybe empty list.
        
        # --- REPLACEMENT ---
        slots_needed = self.num_stocks - len(self.kept_isins)
        new_picks = []
        
        if slots_needed > 0:
            for ind in ind_ranked['industry']:
                if len(new_picks) >= slots_needed: break
                
                # CONSTRAINT: New Industry Only
                if ind in held_industries:
                    continue
                    
                ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                ind_universe = ind_universe.sort_values('mc', ascending=False)
                top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
                
                for isin in top_for_ind:
                    if isin not in self.kept_isins and isin not in new_picks:
                        new_picks.append(isin)
                        if len(new_picks) >= slots_needed: break
        
        self.kept_isins.extend(new_picks)
        if not self.kept_isins: return {}
        
        # Equal Weight
        w = 1.0 / len(self.kept_isins)
        return {isin: w for isin in self.kept_isins}
