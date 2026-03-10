#!/usr/bin/env python
"""
Promoter Skin-in-the-Game Strategy (OPTIMIZED)

Optimizations Applied:
1. 15 stocks (instead of 20) - based on portfolio size analysis
2. Liquidity Filter: Min Daily Value > 0.005% of Market Cap
3. 4 stocks per industry cap (from hierarchical champion)

Logic:
1. Filter: Stocks with increasing promoter percentage over a 4-quarter lookback.
2. Liquidity: Only stocks meeting minimum liquidity threshold
3. Ranking: Rank those stocks by their parent Industry's Relative Strength (RS vs Top 1000).
4. Selection: Top 15 stocks (max 4 per industry).
5. Portfolio: Equal weight per stock, 5% cash interest (30% tax).
6. Universe: Restricted to TOP 1000 stocks by Market Cap on rebalance date.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class PromoterSkinInGameOptimized:
    def __init__(self):
        print("="*100)
        print("PROMOTER SKIN-IN-THE-GAME + INDUSTRY RS (OPTIMIZED)")
        print("15 STOCKS | 0.005% LIQUIDITY FILTER | 4 PER INDUSTRY CAP")
        print("="*100)
        self.base_path = Path(__file__).parent.parent.parent
        self.database_path = self.base_path / 'database'
        self.benchmark_path = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
        self.LOOKBACK_QUARTERS = 4
        self.RS_LOOKBACK_DAYS = 126 # ~6 months
        self.NUM_STOCKS = 15  # Optimized from 20
        self.MAX_PER_INDUSTRY = 4  # From hierarchical champion
        self.MAX_WEIGHT = 0.10  # 10% max weight (from champion)
        self.INTEREST_RATE = 0.05
        self.TAX_RATE = 0.30
        self.INITIAL_CAPITAL = 10000000
        self.MIN_TURNOVER_PCT = 0.005  # 0.005% liquidity filter
        
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
        
        # Precompute volume data for liquidity filter
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.volume_values = {}
        for isin, group in self.price_df.groupby('isin'):
            sorted_group = group.sort_values('date')
            self.volume_values[isin] = dict(zip(sorted_group['date'], sorted_group['volume']))
        
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
        self.shp_with_info = self.shp_df.merge(self.industry_df[['isin', 'industry', 'industry_group']], on='isin', how='left')
        self.shp_with_info = self.shp_with_info.dropna(subset=['quarter_date', 'industry', 'industry_group'])
        self.shp_with_info = self.shp_with_info.sort_values(['isin', 'quarter_date'])
        
        # Promoter increase over 4 quarters
        self.shp_with_info['prev_promoter'] = self.shp_with_info.groupby('isin')['promoter_holding_pct'].shift(self.LOOKBACK_QUARTERS)
        self.shp_with_info['promoter_buying'] = (self.shp_with_info['promoter_holding_pct'] - self.shp_with_info['prev_promoter']) > 0
        
        # Prices setup
        self.bench_df['date'] = pd.to_datetime(self.bench_df['date'])
        self.bench_df = self.bench_df.sort_values('date')
        
        self.price_dates = {}; self.price_values = {}
        for isin, group in self.price_df.groupby('isin'):
            self.price_dates[isin] = group.sort_values('date')['date'].values
            self.price_values[isin] = group.sort_values('date')['close'].values
            
    def get_min_value(self, isin, date):
        """Get minimum daily value over past 30 days"""
        start = date - pd.Timedelta(days=30)
        relevant_dates = [d for d in self.volume_values.get(isin, {}).keys() if start <= d <= date]
        if not relevant_dates: return 0
        
        values = []
        for d in relevant_dates:
            vol = self.volume_values[isin].get(d, 0)
            price = self.get_price(isin, d)
            if price and vol > 0:
                values.append(vol * price)
        
        return np.min(values) if values else 0
    
    def get_ret_for_isins(self, isins, date, lookback_days):
        if not isins: return 0
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

    def calculate_selection(self, date):
        # 1. TOP 1000 UNIVERSE ON THIS DATE
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        top_1000_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(1000)['isin'].tolist()

        # 2. LIQUIDITY FILTER
        liquid_isins = []
        for isin in top_1000_isins:
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
        
        # Only stocks with increasing promoter holdings
        candidate_data = recent[recent['promoter_buying'] == True]
        if candidate_data.empty: return []

        # 4. INDUSTRY RS RANKING (STRICTLY TOP 1000 MEMBERS)
        industries = candidate_data['industry'].unique()
        bench_ret = self.get_bench_ret(date, self.RS_LOOKBACK_DAYS)
        ind_rs = {}
        for ind in industries:
            # ONLY use Top 1000 members of this industry to calculate its RS
            ind_isins = self.industry_df[(self.industry_df['industry'] == ind) & (self.industry_df['isin'].isin(top_1000_isins))]['isin'].tolist()
            ind_ret = self.get_ret_for_isins(ind_isins, date, self.RS_LOOKBACK_DAYS)
            ind_rs[ind] = ind_ret - bench_ret
        
        # 5. RANK STOCKS BY INDUSTRY RS, APPLY 4-PER-INDUSTRY CAP
        candidate_data['ind_rs'] = candidate_data['industry'].map(ind_rs)
        candidate_data = candidate_data.merge(p_slice[['isin', 'mc']], on='isin', how='left')
        candidate_data = candidate_data.sort_values(by=['ind_rs', 'mc'], ascending=False)
        
        # Apply 4-per-industry cap
        selected = []
        industry_counts = {}
        for _, row in candidate_data.iterrows():
            ind = row['industry']
            if industry_counts.get(ind, 0) < self.MAX_PER_INDUSTRY:
                selected.append(row['isin'])
                industry_counts[ind] = industry_counts.get(ind, 0) + 1
                if len(selected) >= self.NUM_STOCKS:
                    break
        
        return selected

    def get_price(self, isin, date):
        if isin not in self.price_dates: return None
        idx = np.searchsorted(self.price_dates[isin], np.datetime64(date), side='right') - 1
        return self.price_values[isin][idx] if idx >= 0 else None

    def run(self):
        dates = pd.date_range('2017-05-01', '2025-11-15', freq='QS-FEB')
        portfolio = {}; cash = self.INITIAL_CAPITAL; equity = []; prev_date = dates[0]
        
        for i, date in enumerate(dates):
            if i > 0:
                interest = cash * (self.INTEREST_RATE * (date - prev_date).days / 365.25) * (1 - self.TAX_RATE)
                cash += interest
            
            p_val = sum([h['shares'] * (self.get_price(isin, date) or 0) for isin, h in portfolio.items()])
            curr_val = cash + p_val
            
            stocks = self.calculate_selection(date)
            if not stocks:
                print(f"[{date.date()}] Value: ₹{curr_val:,.0f} | Ratio: 0% | Stocks: 0")
                equity.append({'date': date, 'value': curr_val})
                prev_date = date
                continue
            
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
        print(f"\nPROMOTER RS OPTIMIZED RETURN: {ret:.2f}%")
        p = self.base_path / 'strategies' / 'new_research' / 'outputs'
        p.mkdir(parents=True, exist_ok=True)
        res.to_csv(p / f'promoter_skin_in_game_optimized_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', index=False)

if __name__ == "__main__":
    PromoterSkinInGameOptimized().run()
