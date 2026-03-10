#!/usr/bin/env python
"""
Final Contrarian Shareholders Decrease Strategy - TOP 500 VERSION (SYNC-15 + SMALL-CAP TILT)
Logic:
Identical to Top 500 Baseline but with:
1. Selection: Bottom 4 stocks by Market Cap per industry (Small-cap tilt)
"""

from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.contrarian_sync15_top500 import ContrarianSync15Top500

class ContrarianSync15Top500SmallCap(ContrarianSync15Top500):
    def __init__(self):
        super().__init__(benchmark_file='benchmark_top500_equal_weight_2016-02-01_to_2026-02-09.csv', universe_size=500)
    
    def calculate_selection(self, date):
        # Override selection to use ascending=True for market cap (Small-Cap Tilt)
        import pandas as pd
        import numpy as np

        # 1. DEFINE UNIVERSE (Top N + Liquid)
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        universe_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(self.UNIVERSE_SIZE)['isin'].tolist()

        liquid_isins = []
        mcap_map = dict(zip(p_slice['isin'], p_slice['mc']))
        for isin in universe_isins:
            val = self.get_min_value(isin, date)
            mcap = mcap_map.get(isin, 0)
            if mcap > 0 and (val / mcap * 100) >= 0.005:
                liquid_isins.append(isin)

        # 2. SENTIMENT FILTERS
        cut = date - pd.Timedelta(days=120)
        recent = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date)].copy()
        if recent.empty: return []
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()

        # Group Level (Top 40%)
        g_metrics = recent.groupby('industry_group').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        g_metrics = g_metrics[g_metrics['tot'] >= 5]
        if g_metrics.empty: return []
        g_metrics['pct'] = g_metrics['dec'] / g_metrics['tot'] * 100
        top_groups = g_metrics.sort_values('pct', ascending=False).head(max(int(len(g_metrics)*0.4), 1))['industry_group'].tolist()
        
        # Industry Level (60% ABS)
        i_metrics = recent[recent['industry_group'].isin(top_groups)].groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        i_metrics['pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
        i_metrics = i_metrics[i_metrics['tot'] >= 3]
        eligible_inds = i_metrics[i_metrics['pct'] >= 60.0]['industry'].tolist()
        if not eligible_inds: return []
        
        # OPTIONAL: RSNP THRESHOLD FILTER
        rsnp_threshold = getattr(self, 'RSNP_THRESHOLD_FILTER', 0.0)
        
        if rsnp_threshold > 0:
            rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
            
            # Use universe benchmark for RSNP calc
            if hasattr(self, 'universe_bench'):
                end_bench = self.universe_bench[self.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
                start_date_bench = rs_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
                start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
                bench_ret = (end_bench / start_bench) - 1
            else:
                bench_ret = self.get_universe_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)
                
            passed_inds = []
            for ind in eligible_inds:
                # calculate_rsnp is available from grandparent class
                rsnp = self.calculate_rsnp(ind, rs_date, self.RS_LOOKBACK_DAYS, bench_ret)
                if rsnp >= rsnp_threshold:
                    passed_inds.append(ind)
            eligible_inds = passed_inds
            
        if not eligible_inds: return []
        
        # 3. RSNP RANKING (with Lag)
        rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
        univ_bench_ret = self.get_universe_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)
        rs_results = []
        for ind in eligible_inds:
            rsnp = self.calculate_rsnp(ind, rs_date, self.RS_LOOKBACK_DAYS, univ_bench_ret)
            rs_results.append({'industry': ind, 'rsnp': rsnp})
        
        rs_df = pd.DataFrame(rs_results)
        ranked_inds = rs_df.sort_values('rsnp', ascending=False)['industry'].tolist()
        
        # 4. FINAL STOCK SELECTION (Small-Cap Tilt)
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in liquid_isins]
            # Key difference: ascending=True for MC
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=True)
            pick = ind_pool.head(4)['isin'].tolist()
            
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

if __name__ == "__main__":
    ContrarianSync15Top500SmallCap().run()
