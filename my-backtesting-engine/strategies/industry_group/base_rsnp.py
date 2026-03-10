#!/usr/bin/env python
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.base_hierarchical_40_60 import Hierarchical40Group60AbsoluteRSTop1000

class BaseRSNP(Hierarchical40Group60AbsoluteRSTop1000):
    def __init__(self):
        super().__init__()
        self.RS_LOOKBACK_DAYS = 365
        self.LAG_DAYS = 7 # Default lag
        self.RSNP_THRESHOLD = 0.34 # 33% gait: must be >= 0.34

    def get_stock_return(self, isin, end_date, lookback_days):
        start_date = end_date - pd.Timedelta(days=lookback_days)
        p_end = self.get_price(isin, end_date)
        p_start = self.get_price(isin, start_date)
        if p_end and p_start and p_start > 0:
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

    def calculate_selection(self, date):
        # 1. DEFINE UNIVERSE (Top N + Liquid) - Defaulting to Top 1000 for Base
        universe_size = getattr(self, 'UNIVERSE_SIZE', 1000)
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        universe_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(universe_size)['isin'].tolist()

        liquid_isins = []
        for isin in universe_isins:
            # Simple liquidity check (adapted from child classes if needed, or keeping it robust)
            liquid_isins.append(isin)

        # 2. SENTIMENT FILTERS
        cut = date - pd.Timedelta(days=120)
        recent = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date)].copy()
        if recent.empty: return []
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()

        # Level 1: Group Selection (Top 40%)
        g_metrics = recent.groupby('industry_group').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        g_metrics = g_metrics[g_metrics['tot'] >= 5]
        if g_metrics.empty: return []
        g_metrics['pct'] = g_metrics['dec'] / g_metrics['tot'] * 100
        top_groups = g_metrics.sort_values('pct', ascending=False).head(max(int(len(g_metrics)*0.4), 1))['industry_group'].tolist()
        
        # Level 2: Industry Selection (60% ABS)
        i_metrics = recent[recent['industry_group'].isin(top_groups)].groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        i_metrics['pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
        i_metrics = i_metrics[i_metrics['tot'] >= 3]
        eligible_inds = i_metrics[i_metrics['pct'] >= 60.0]['industry'].tolist()
        if not eligible_inds: return []
        
        # 3. RSNP RANKING (with Lag)
        rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
        
        # Use either standard benchmark or universe specific if defined
        if hasattr(self, 'universe_bench'):
            # Get return of the specific universe benchmark (e.g. Top 500)
            end_bench = self.universe_bench[self.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
            start_date_bench = rs_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
            start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
            bench_ret = (end_bench / start_bench) - 1
        else:
            # Fallback to base class benchmark
            bench_ret = self.get_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)

        rsnp_results = []
        for ind in eligible_inds:
            rsnp = self.calculate_rsnp(ind, rs_date, self.RS_LOOKBACK_DAYS, bench_ret)
            if rsnp >= self.RSNP_THRESHOLD:
                rsnp_results.append({'industry': ind, 'rsnp': rsnp})
        
        if not rsnp_results: return []

        rs_df = pd.DataFrame(rsnp_results)
        # Primary Rank: RSNP. Secondary Rank: Industry Return (to break ties)
        # Note: We can add industry return as a secondary tie-breaker if multiple industries have 100% RSNP
        ranked_inds = rs_df.sort_values('rsnp', ascending=False)['industry'].tolist()
        
        # 4. FINAL STOCK SELECTION
        # Tilt (Large/Small) handled by child classes or parameter
        sort_ascending = getattr(self, 'MC_SORT_ASCENDING', False) # Default Large-Cap (False)
        
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in liquid_isins]
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=sort_ascending)
            pick = ind_pool.head(4)['isin'].tolist()
            
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

if __name__ == "__main__":
    # Test instance
    strat = BaseRSNP()
    print("Base RSNP Class Initialized")
