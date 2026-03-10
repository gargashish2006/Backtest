#!/usr/bin/env python
"""
Promoter Strategy - Top 500 Universe Transition
Final Optimized + PB + SL + TOP 500
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.new_research.promoter_skin_in_game_pb import PromoterSkinInGameProfitBooking

class PromoterSkinInGameTop500(PromoterSkinInGameProfitBooking):
    def __init__(self):
        super().__init__()
        print("=" * 100)
        print("SWITCHING UNIVERSE TO TOP 500 MARKET CAP")
        print("=" * 100)

    def calculate_selection(self, date):
        # 1. TOP 500 UNIVERSE ON THIS DATE
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        
        # KEY CHANGE: .head(500)
        top_500_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(500)['isin'].tolist()

        # 2. LIQUIDITY FILTER
        liquid_isins = []
        for isin in top_500_isins:
            val = self.get_min_value(isin, date)
            p = self.get_price(isin, date)
            shares = self.shares_map.get(isin, 0)
            
            if p and shares > 0:
                mcap = p * shares
                if mcap > 0:
                    ratio = (val / mcap) * 100
                    if ratio >= self.MIN_TURNOVER_PCT:
                        liquid_isins.append(isin)

        # 3. PROMOTER FILTER (LIQUID STOCKS ONLY)
        cut = date - pd.Timedelta(days=120)
        recent = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date) & (self.shp_with_info['isin'].isin(liquid_isins))].copy()
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()
        
        # Promoter Buying is True
        pool = recent[recent['promoter_buying'] == True]['isin'].tolist()
        if not pool: return []
        
        # 4. RANK BY INDUSTRY RS
        industries = self.industry_df[self.industry_df['isin'].isin(pool)]['industry'].unique()
        ind_rs = {}
        bench_ret = self.get_bench_ret(date, self.RS_LOOKBACK_DAYS)
        
        for ind in industries:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            # Industry RS is calculated against the Top 1000 benchmark for consistency
            ret = self.get_ret_for_isins(ind_isins, date, self.RS_LOOKBACK_DAYS)
            ind_rs[ind] = ret - bench_ret
            
        # Select stocks
        pool_df = pd.DataFrame({'isin': pool})
        pool_df = pool_df.merge(self.industry_df[['isin', 'industry']], on='isin')
        pool_df['ind_rs'] = pool_df['industry'].map(ind_rs)
        pool_df = pool_df.sort_values('ind_rs', ascending=False)
        
        selected = []
        ind_counts = {}
        for _, row in pool_df.iterrows():
            ind = row['industry']
            if ind_counts.get(ind, 0) < self.MAX_PER_INDUSTRY:
                selected.append(row['isin'])
                ind_counts[ind] = ind_counts.get(ind, 0) + 1
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

if __name__ == "__main__":
    PromoterSkinInGameTop500().run()
