#!/usr/bin/env python
import pandas as pd
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_momentum.base_momentum import BaseIndustryMomentum

class IM_Hybrid_Small(BaseIndustryMomentum):
    def __init__(self):
        super().__init__()
        self.UNIVERSE_SIZE = 1000
        self.MC_SORT_ASCENDING = True # Small-Cap Tilt
        self.NUM_STOCKS = 15

    def calculate_selection(self, date):
        # 1. DEFINE UNIVERSE (Top 1000)
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        universe_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(self.UNIVERSE_SIZE)['isin'].tolist()
        
        # 2. SHAREHOLDER DATA (Last 120 days)
        cut = date - pd.Timedelta(days=120)
        recent_shp = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date)].copy()
        recent_shp = recent_shp.sort_values('quarter_date').groupby('isin').last().reset_index()

        # 3. CALCULATE SHAREHOLDER FACTOR per Industry
        i_metrics = recent_shp.groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        i_metrics['sh_pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
        eligible_shp_inds = i_metrics[i_metrics['sh_pct'] >= 60.0]['industry'].tolist()

        # 4. RSNP RANKING (with 7-day Lag)
        rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
        bench_ret = self.get_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)
        
        rsnp_results = []
        # We only rank industries that passed the 60% SHP gait
        for ind in eligible_shp_inds:
            rsnp = self.calculate_rsnp(ind, rs_date, self.RS_LOOKBACK_DAYS, bench_ret)
            ind_ret = self.get_industry_ret(ind, rs_date, self.RS_LOOKBACK_DAYS)
            rsnp_results.append({'industry': ind, 'rsnp': rsnp, 'avg_ret': ind_ret})
        
        if not rsnp_results: return []

        rs_df = pd.DataFrame(rsnp_results)
        # Rank by RSNP, then Avg Return
        ranked_inds = rs_df.sort_values(['rsnp', 'avg_ret'], ascending=False)['industry'].tolist()
        
        # 5. FINAL STOCK SELECTION (Small-Cap Tilt)
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in universe_isins]
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=self.MC_SORT_ASCENDING)
            
            # Max 4 stocks per industry
            pick = ind_pool.head(4)['isin'].tolist()
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

if __name__ == "__main__":
    print("====================================================================================================")
    print("HYBRID INDUSTRY MOMENTUM - RSNP + 60% SHP FILTER + TOP 1000 + SMALL-CAP TILT")
    print("====================================================================================================")
    IM_Hybrid_Small().run()
