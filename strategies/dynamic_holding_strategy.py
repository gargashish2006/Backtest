
import pandas as pd
from typing import Dict, List, Optional
from strategies.contrarian_breadth import ContrarianBreadthStrategy

class DynamicHoldingStrategy(ContrarianBreadthStrategy):
    """
    Extends ContrarianBreadthStrategy to support DYNAMIC HOLDING periods.
    Stocks are held until a specific EXIT SIGNAL is triggered, regardless of rank.
    """
    def __init__(self, data_handler, 
                 exit_mode: str = 'thesis_breach',  # 'thesis_breach' | 'momentum_loss' | 'rank_decay'
                 **kwargs):
        super().__init__(data_handler, **kwargs)
        self.exit_mode = exit_mode
        self.kept_isins = [] # State: List of ISINs currently held
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Run Standard Champion Logic to get the "Fresh List" (Candidates)
        # We need the full ranked list, not just top 15.
        # But base class returns weights. Let's replicate the core logic steps.
        
        # --- REPLICATING CORE SELECTION LOGIC ---
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        # Universe & Liquidity
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

        # Shareholder Filter
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # Industry Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        # Industry Filter
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
        
        # --- STATEFUL LOGIC START ---
        
        # 1. Process Existing Holdings (Check for Exits)
        holdings_to_check = list(self.kept_isins)
        self.kept_isins = [] # Reset, re-add survivors
        
        for isin in holdings_to_check:
            keep = True
            
            # EXIT 1: Thesis Breach (Shareholder Increase)
            if self.exit_mode == 'thesis_breach':
                # Check most recent shareholder trend. If 'decreased' == False (i.e., increased or flat), sell.
                # Actually, check if 'value_counts' increased > 5%?
                # The sh_trend dataframe has 'diff_pct' if used get_shareholder_trend?
                # Simpler: If it's not in the 'sh_trend' filtered list (which requires decrease), 
                # effectively it has increased or data missing.
                # But 'sh_trend' above is for Universe. Existing holding might be outside filtered uni.
                
                # Check specific stock trend
                trend_row = sh_trend[sh_trend['isin'] == isin]
                if not trend_row.empty:
                    # Current logic: 'decreased' is boolean (True if < -0.01%)
                    if trend_row['decreased'].iloc[0] == False:
                        keep = False
                else:
                    # Data missing? Keep for safety or Sell? Sell if no data.
                    keep = False
                    
            # EXIT 2: Momentum Loss (RSNP < 0)
            elif self.exit_mode == 'momentum_loss':
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                     stock_ret = (p1/p0) - 1
                     if stock_ret < bench_return:
                         keep = False
                else:
                    keep = False # Missing price data
                    
            # EXIT 3: Rank Decay (Top 50)
            elif self.exit_mode == 'rank_decay':
                # Determine its current rank
                current_rank = 999
                # Helper to find rank in the calculated universe
                rank_counter = 0
                found = False
                
                # Iterate through ranked industries and stocks to find ISIN
                # This is computationally heavy but accurate
                for ind in ind_ranked['industry']:
                    ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                    ind_universe = ind_universe.sort_values('mc', ascending=False)
                    # Note: Original selection picks top 3 per industry.
                    # We should count how many stocks would be picked before this one.
                    # Simplified: If it's in the qualified industries, check its MC rank?
                    # Let's say: Is it in the top 50 stocks that WOULD be picked by the algo?
                    
                    top_per_ind = ind_universe.head(self.max_per_industry)
                    for candidate_isin in top_per_ind['isin']:
                        rank_counter += 1
                        if candidate_isin == isin:
                            current_rank = rank_counter
                            found = True
                            break
                    if found: break
                
                if current_rank > 50:
                    keep = False
                    
            if keep:
                self.kept_isins.append(isin)
                
        # 2. Fill Empty Slots
        slots_needed = self.num_stocks - len(self.kept_isins)
        new_picks = []
        
        if slots_needed > 0:
            for ind in ind_ranked['industry']:
                if len(new_picks) >= slots_needed: break
                ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                ind_universe = ind_universe.sort_values('mc', ascending=False)
                top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
                
                for isin in top_for_ind:
                    # Prevent duplicates
                    if isin not in self.kept_isins and isin not in new_picks:
                        new_picks.append(isin)
                        if len(new_picks) >= slots_needed: break
        
        # 3. Final List Update
        self.kept_isins.extend(new_picks)
        
        # 4. Weighting
        if not self.kept_isins: return {}
        w = 1.0 / len(self.kept_isins)
        return {isin: w for isin in self.kept_isins}
