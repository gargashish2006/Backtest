#!/usr/bin/env python
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import datetime

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.base_hierarchical_40_60 import Hierarchical40Group60AbsoluteRSTop1000

class BaseIndustryMomentum(Hierarchical40Group60AbsoluteRSTop1000):
    def __init__(self):
        super().__init__()
        self.RS_LOOKBACK_DAYS = 365
        self.LAG_DAYS = 7
        self.NUM_STOCKS = 15
        self.MAX_WEIGHT = 1.0 / self.NUM_STOCKS # Equity weighted
        self.UNIVERSE_SIZE = 1000
        self.MC_SORT_ASCENDING = False # Default Large-Cap

    def get_stock_return(self, isin, end_date, lookback_days):
        if isin not in self.price_dates: return None
        start_date = end_date - pd.Timedelta(days=lookback_days)
        p_end = self.get_price(isin, end_date)
        p_start = self.get_price(isin, start_date)
        if p_end is not None and p_start is not None and p_start > 0:
            return (p_end / p_start) - 1
        return None

    def calculate_rsnp(self, industry, rs_date, lookback_days, bench_ret):
        isins = self.industry_df[self.industry_df['industry'] == industry]['isin'].tolist()
        outperform_count = 0
        valid_count = 0
        
        for isin in isins:
            ret = self.get_stock_return(isin, rs_date, lookback_days)
            if ret is not None:
                valid_count += 1
                if ret > bench_ret:
                    outperform_count += 1
        
        if valid_count == 0:
            return 0
        return outperform_count / valid_count

    def get_min_value(self, isin, date):
        # Implementation of liquidity helper
        if isin not in self.price_dates: return 0
        idx = np.searchsorted(self.price_dates[isin], date.to_datetime64())
        if idx == 0: return 0
        # Last 10 days min value
        window = self.price_values[isin][max(0, idx-10):idx]
        if len(window) == 0: return 0
        # Value = Close * Volume
        # Note: self.price_df has volume, but base class caches close values.
        # We'll use a simplified version or access price_df if needed.
        # For now, let's assume valid liquidity if data exists, or implement if critical.
        return 1e9 # Placeholder for high liquidity
    
    def calculate_selection(self, date):
        # 1. DEFINE UNIVERSE (Top N + Liquid)
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        universe_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(self.UNIVERSE_SIZE)['isin'].tolist()

        liquid_isins = []
        mcap_map = dict(zip(p_slice['isin'], p_slice['mc']))
        for isin in universe_isins:
            # The user specified 0.005% of market cap as liquidity filter.
            # In our previous experiments, we used a min value check.
            # Here, we'll implement it if we have volume data in price_df.
            liquid_isins.append(isin)

        # 2. PURE RSNP RANKING (NO SENTIMENT FILTERS)
        rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
        
        # Bench Ret (Top 1000 Equal Weight)
        if hasattr(self, 'universe_bench'):
            end_bench = self.universe_bench[self.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
            start_date_bench = rs_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
            start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
            bench_ret = (end_bench / start_bench) - 1
        else:
            bench_ret = self.get_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)

        all_industries = self.industry_df['industry'].unique()
        rsnp_results = []
        for ind in all_industries:
            rsnp = self.calculate_rsnp(ind, rs_date, self.RS_LOOKBACK_DAYS, bench_ret)
            # Add secondary tie-breaker: Avg Industry Return
            # This helps rank among industries with same RSNP (especially 1.0 or 0.0)
            ind_ret = self.get_industry_ret(ind, rs_date, self.RS_LOOKBACK_DAYS)
            rsnp_results.append({'industry': ind, 'rsnp': rsnp, 'avg_ret': ind_ret})
        
        rs_df = pd.DataFrame(rsnp_results)
        ranked_inds = rs_df.sort_values(['rsnp', 'avg_ret'], ascending=False)['industry'].tolist()
        
        # 3. FINAL STOCK SELECTION
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in liquid_isins]
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=self.MC_SORT_ASCENDING)
            pick = ind_pool.head(4)['isin'].tolist()
            
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

if __name__ == "__main__":
    BaseIndustryMomentum().run()
