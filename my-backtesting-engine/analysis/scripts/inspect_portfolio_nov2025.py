#!/usr/bin/env python
"""
Portfolio Inspector - Show holdings at November 2025 rebalance
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class PortfolioInspector:
    def __init__(self):
        self.base_path = Path(__file__).parent.parent.parent
        self.database_path = self.base_path / 'database'
        self.benchmark_path = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
        self.LOOKBACK_QUARTERS = 4
        self.RS_LOOKBACK_DAYS = 126
        self.NUM_STOCKS = 15
        
        self.load_data()
        self.preprocess_data()
        
    def load_data(self):
        self.price_df = pd.read_parquet(self.database_path / 'price_data.parquet')
        self.shp_df = pd.read_parquet(self.database_path / 'shareholding_patterns.parquet')
        self.industry_df = pd.read_parquet(self.database_path / 'industry_info.parquet')
        self.bench_df = pd.read_csv(self.benchmark_path)
        
        if (self.database_path / 'outstanding_shares.csv').exists():
            shares = pd.read_csv(self.database_path / 'outstanding_shares.csv')
            self.shares_map = dict(zip(shares['isin'], shares['total_outstanding_shares']))
        else:
            latest = self.shp_df.sort_values('quarter').groupby('isin').last().reset_index()
            self.shares_map = dict(zip(latest['isin'], latest['total_outstanding_shares']))
        
    def parse_date(self, q):
        try:
            p = str(q).split('-')
            m_map = {'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12, 'March': 3, 'June': 6, 'September': 9, 'December': 12}
            m = m_map.get(p[0], 12); y = int(p[1])
            from calendar import monthrange
            return pd.Timestamp(year=y, month=m, day=monthrange(y, m)[1])
        except: return pd.NaT

    def preprocess_data(self):
        self.shp_df['quarter_date'] = self.shp_df['quarter'].apply(self.parse_date)
        self.shp_with_info = self.shp_df.merge(self.industry_df[['isin', 'industry', 'industry_group', 'company_name']], on='isin', how='left')
        self.shp_with_info = self.shp_with_info.dropna(subset=['quarter_date', 'industry', 'industry_group'])
        self.shp_with_info = self.shp_with_info.sort_values(['isin', 'quarter_date'])
        
        self.shp_with_info[f'prev_sh'] = self.shp_with_info.groupby('isin')['total_shareholders'].shift(self.LOOKBACK_QUARTERS)
        self.shp_with_info[f'decreasing'] = (self.shp_with_info['total_shareholders'] - self.shp_with_info[f'prev_sh']) < 0
        
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.bench_df['date'] = pd.to_datetime(self.bench_df['date'])
        self.bench_df = self.bench_df.sort_values('date')
        
        self.price_dates = {}; self.price_values = {}
        for isin, group in self.price_df.groupby('isin'):
            self.price_dates[isin] = group.sort_values('date')['date'].values
            self.price_values[isin] = group.sort_values('date')['close'].values
            
    def get_industry_ret(self, industry, date, lookback_days):
        isins = self.industry_df[self.industry_df['industry'] == industry]['isin'].tolist()
        start_date = date - pd.Timedelta(days=lookback_days)
        returns = []
        for isin in isins:
            p_end = self.get_price(isin, date)
            p_start = self.get_price(isin, start_date)
            if p_end and p_start and p_start > 0:
                returns.append((p_end / p_start) - 1)
        return np.mean(returns) if returns else 0

    def get_bench_ret(self, date, lookback_days):
        start_date = date - pd.Timedelta(days=lookback_days)
        end_val = self.bench_df[self.bench_df['date'] <= date].iloc[-1]['index_value']
        start_val = self.bench_df[self.bench_df['date'] <= start_date].iloc[-1]['index_value']
        return (end_val / start_val) - 1

    def get_qualifying_industries(self, date):
        cut = date - pd.Timedelta(days=120)
        recent = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date)].copy()
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()
        if recent.empty: return []

        g_metrics = recent.groupby('industry_group').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        g_metrics = g_metrics[g_metrics['tot'] >= 5]
        if g_metrics.empty: return []
        g_metrics['pct'] = g_metrics['dec'] / g_metrics['tot'] * 100
        top_groups = g_metrics.sort_values('pct', ascending=False).head(max(int(len(g_metrics)*0.5), 1))['industry_group'].tolist()
        
        i_metrics = recent[recent['industry_group'].isin(top_groups)].groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        i_metrics['pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
        i_metrics = i_metrics[i_metrics['tot'] >= 3]
        cand_inds_df = i_metrics[i_metrics['pct'] > 60.0]
        if cand_inds_df.empty: return []
        
        bench_ret = self.get_bench_ret(date, self.RS_LOOKBACK_DAYS)
        rs_results = []
        for ind in cand_inds_df['industry']:
            ind_ret = self.get_industry_ret(ind, date, self.RS_LOOKBACK_DAYS)
            rs = ind_ret - bench_ret
            rs_results.append({'industry': ind, 'rs': rs, 'ind_ret': ind_ret})
        
        if not rs_results:
            return pd.DataFrame()
        
        rs_df = pd.DataFrame(rs_results)
        return rs_df.sort_values('rs', ascending=False)

    def calculate_selection(self, date):
        ranked_inds_df = self.get_qualifying_industries(date)
        if ranked_inds_df.empty:
            return []
        
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        top_1000_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(1000)['isin'].tolist()
        
        universe_pool = p_slice[p_slice['isin'].isin(top_1000_isins)].merge(
            self.industry_df[['isin', 'industry', 'company_name']], 
            on='isin',
            how='left'
        ).sort_values('mc', ascending=False)
        
        selected = []
        for _, row in ranked_inds_df.iterrows():
            ind = row['industry']
            stocks = universe_pool[universe_pool['industry'] == ind].head(4)
            for _, stock in stocks.iterrows():
                selected.append({
                    'isin': stock['isin'],
                    'company': stock['company_name_y'],  # from industry_df
                    'industry': ind,
                    'rs': row['rs'],
                    'ind_return_6m': row['ind_ret'],
                    'market_cap': stock['mc'],
                    'price': stock['close']
                })
            if len(selected) >= self.NUM_STOCKS:
                break
        
        return selected[:self.NUM_STOCKS]

    def get_price(self, isin, date):
        if isin not in self.price_dates: return None
        idx = np.searchsorted(self.price_dates[isin], np.datetime64(date), side='right') - 1
        return self.price_values[isin][idx] if idx >= 0 else None

    def inspect(self):
        date = pd.Timestamp('2025-11-01')
        print("="*100)
        print(f"PORTFOLIO COMPOSITION AT {date.date()}")
        print("="*100)
        
        portfolio = self.calculate_selection(date)
        
        if not portfolio:
            print("No stocks selected!")
            return
        
        df = pd.DataFrame(portfolio)
        
        print(f"\nTotal Stocks: {len(df)}")
        print(f"Industries: {df['industry'].nunique()}")
        print(f"\nIndustries Selected (by RS ranking):")
        ind_summary = df.groupby('industry').agg({
            'rs': 'first',
            'ind_return_6m': 'first',
            'company': 'count'
        }).rename(columns={'company': 'num_stocks'}).sort_values('rs', ascending=False)
        
        for ind, row in ind_summary.iterrows():
            print(f"  {ind:50s} | RS: {row['rs']:+.2%} | 6M Ret: {row['ind_return_6m']:+.2%} | Stocks: {int(row['num_stocks'])}")
        
        print(f"\n{'Company':<50s} {'Industry':<40s} {'Market Cap (Cr)':<15s} {'Price':<10s}")
        print("-"*120)
        for _, stock in df.iterrows():
            print(f"{stock['company']:<50s} {stock['industry']:<40s} {stock['market_cap']/1e7:>12,.0f}   ₹{stock['price']:>8,.2f}")

if __name__ == "__main__":
    PortfolioInspector().inspect()
