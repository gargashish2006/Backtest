#!/usr/bin/env python
"""
Final Contrarian Shareholders Decrease Strategy - TOP 500 VERSION (SYNC-15 REFINED)
Hierarchy:
1. Universe: Top 500 Market Cap
2. Timing: Rebalance on 15th of Feb/May/Aug/Nov
3. RS Signal: Industry Benchmark Return vs Top 500 Benchmark Return (Synchronized)
4. RS Lookback: 1 Year (365 Days)
5. Group Level: Top 40% Industry Groups by % stocks with decreasing shareholders
6. Industry Level: Industries within those groups with >= 60% stocks showing decrease
7. Selection: Top 4 stocks by Market Cap per industry (Max 15 total)
8. NO Profit Booking or Stop-Loss
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

from strategies.industry_group.base_hierarchical_40_60 import Hierarchical40Group60AbsoluteRSTop1000

class ContrarianSync15Top500(Hierarchical40Group60AbsoluteRSTop1000):
    def __init__(self, benchmark_file='Benchmark_500_equalWeight.csv', universe_size=500, lag_days=0):
        super().__init__()
        self.UNIVERSE_SIZE = universe_size
        self.RS_LOOKBACK_DAYS = 365
        self.LAG_DAYS = lag_days
        
        # Load Universe Benchmark
        bench_file = self.base_path / f'analysis/outputs/benchmarks/{benchmark_file}'
        self.universe_bench = pd.read_csv(bench_file)
        self.universe_bench['date'] = pd.to_datetime(self.universe_bench['date'])
        self.universe_bench = self.universe_bench.sort_values('date')
        
        # Pre-load Industry Benchmarks
        self.industry_bench_data = {}
        self.ind_bench_root = self.base_path / 'analysis/outputs/benchmarks/industries'
        
        print("=" * 100)
        print(f"CONTRARIAN FINAL (SYNC-15): TOP {self.UNIVERSE_SIZE}")
        print(f"RS Methodology: Industry Benchmark vs Universe Benchmark")
        print("=" * 100)

    def load_data(self):
        super().load_data()
        # Build Value Traded Map
        if 'volume' in self.price_df.columns:
            self.price_df['val_traded'] = self.price_df['close'] * self.price_df['volume']
            self.value_dates = {}
            self.value_values = {}
            for isin, group in self.price_df.groupby('isin'):
                sorted_group = group.sort_values('date')
                self.value_dates[isin] = sorted_group['date'].values
                self.value_values[isin] = sorted_group['val_traded'].values
        else:
            self.value_values = None

    def get_ind_bench_ret(self, industry, date, lookback_days):
        if industry not in self.industry_bench_data:
            folder_name = industry.replace(' ', '_').replace('/', '_')
            path = self.ind_bench_root / folder_name / 'timeseries.csv'
            if path.exists():
                df = pd.read_csv(path)
                df['date'] = pd.to_datetime(df['date'])
                self.industry_bench_data[industry] = df.sort_values('date')
            else:
                return 0
        
        df = self.industry_bench_data[industry]
        
        # Get end value (at date)
        end_mask = df['date'] <= date
        if not end_mask.any(): return 0
        end_val = df[end_mask].iloc[-1]['index_value']
        
        # Get start value (at date - lookback)
        start_date = date - pd.Timedelta(days=lookback_days)
        start_mask = df['date'] <= start_date
        if not start_mask.any(): return 0
        start_val = df[start_mask].iloc[-1]['index_value']
        
        return (end_val / start_val) - 1

    def get_universe_bench_ret(self, date, lookback_days):
        mask = self.universe_bench['date'] <= date
        if not mask.any(): return 0
        
        end_val = self.universe_bench[mask].iloc[-1]['index_value']
        start_date = date - pd.Timedelta(days=lookback_days)
        start_mask = self.universe_bench['date'] <= start_date
        if not start_mask.any(): return 0
        
        start_val = self.universe_bench[start_mask].iloc[-1]['index_value']
        return (end_val / start_val) - 1

    def get_min_value(self, isin, date):
        if not self.value_values or isin not in self.value_dates: return 0
        idx = np.searchsorted(self.value_dates[isin], np.datetime64(date), side='right') - 1
        if idx < 21: return 0
        return np.min(self.value_values[isin][idx-21:idx])

    def calculate_selection(self, date):
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
            # Note: universe_bench is loaded in __init__
            if hasattr(self, 'universe_bench'):
                 # Get return of the specific universe benchmark (e.g. Top 500)
                end_bench = self.universe_bench[self.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
                start_date_bench = rs_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
                start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
                bench_ret = (end_bench / start_bench) - 1
            else:
                bench_ret = self.get_universe_bench_ret(rs_date, self.RS_LOOKBACK_DAYS)
                
            passed_inds = []
            for ind in eligible_inds:
                # We need calculate_rsnp. Does this class have it? 
                # It inherits Hierarchical... which now HAS it (added in previous step).
                # So verify calculate_rsnp is available. Yes.
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

        
        # 4. FINAL STOCK SELECTION
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in liquid_isins]
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=False)
            pick = ind_pool.head(4)['isin'].tolist()
            
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
            
        return selected

    def run(self):
        base_dates = pd.date_range('2017-02-01', '2026-02-01', freq='QS-FEB')
        dates = [d + pd.Timedelta(days=14) for d in base_dates if d >= pd.Timestamp('2017-05-01')]
        
        portfolio = {}; cash = self.INITIAL_CAPITAL; equity = []; prev_date = dates[0]
        
        for i, date in enumerate(dates):
            if i > 0:
                interest = cash * (self.INTEREST_RATE * (date - prev_date).days / 365.25) * (1 - self.TAX_RATE)
                cash += interest
            
            p_val = sum([h['shares'] * (self.get_price(isin, date) or 0) for isin, h in portfolio.items()])
            curr_val = cash + p_val
            
            stocks = self.calculate_selection(date)
            if not stocks:
                cash = curr_val; portfolio = {}
            else:
                target_per_stock = curr_val * min(0.95/len(stocks), self.MAX_WEIGHT)
                cash = curr_val; portfolio = {}
                for isin in stocks:
                    p = self.get_price(isin, date)
                    if p:
                        s = int(target_per_stock / (p * 1.002))
                        if s > 0:
                            portfolio[isin] = {'shares': s}
                            cash -= s * p * 1.002
            
            invested = sum([h['shares'] * (self.get_price(k, date) or 0) for k, h in portfolio.items()])
            val = cash + invested
            equity.append({'date': date, 'value': val})
            print(f"[{date.date()}] Value: ₹{val:,.0f} | Ratio: {invested/val:.1%} | Stocks: {len(portfolio)}")
            prev_date = date

        res = pd.DataFrame(equity)
        ret = (res.iloc[-1]['value']/res.iloc[0]['value'] - 1) * 100
        print(f"\nCONTRARIAN SYNC-15 (Top {self.UNIVERSE_SIZE}) RETURN: {ret:.2f}%")
        p = self.base_path / 'strategies' / 'industry_group' / 'outputs'
        p.mkdir(parents=True, exist_ok=True)
        res.to_csv(p / f'contrarian_sync15_top{self.UNIVERSE_SIZE}_refined_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', index=False)
        return res

if __name__ == "__main__":
    ContrarianSync15Top500().run()
