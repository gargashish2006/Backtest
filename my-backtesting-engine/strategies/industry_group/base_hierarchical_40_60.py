#!/usr/bin/env python
"""
Hierarchical Strategy - Top 40% Group + 60% Absolute Filter + RS + TOP 1000 Universe Filter

Logic:
1. Level 1 (Group): Top 40% Industry Groups by shareholder decrease (4Q).
2. Level 2 (Industry): Within selected Groups, filter Industries where >60% of stocks have 
   decreasing shareholders (4Q).
3. Level 3 (Trend - RS): Rank surviving Industries by Relative Strength (Industry vs Top 1000).
4. STOCK SELECTION: Select Top 4 stocks per industry (by Market Cap) ONLY if they are among 
   the overall TOP 1000 stocks by Market Cap on that date.
5. Max Stocks: Limit to 15 stocks total.
6. Portfolio: 10% weight cap per stock, 5% cash interest (30% tax).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class Hierarchical40Group60AbsoluteRSTop1000:
    def __init__(self):
        print("="*100)
        print("HIERARCHICAL STRATEGY - 40% GROUP + 60% ABSOLUTE + RS + TOP 1000")
        print("="*100)
        self.base_path = Path(__file__).parent.parent.parent
        self.database_path = self.base_path / 'database'
        self.benchmark_path = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
        self.LOOKBACK_QUARTERS = 4
        self.RS_LOOKBACK_DAYS = 365
        self.NUM_STOCKS = 15
        self.MAX_WEIGHT = 0.10
        self.INTEREST_RATE = 0.05
        self.TAX_RATE = 0.30
        self.INITIAL_CAPITAL = 10000000
        
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
        self.shp_with_info = self.shp_df.merge(self.industry_df[['isin', 'industry', 'industry_group']], on='isin', how='left')
        self.shp_with_info = self.shp_with_info.dropna(subset=['quarter_date', 'industry', 'industry_group'])
        self.shp_with_info = self.shp_with_info.sort_values(['isin', 'quarter_date'])
        
        self.shp_with_info[f'prev_sh'] = self.shp_with_info.groupby('isin')['total_shareholders'].shift(self.LOOKBACK_QUARTERS)
        self.shp_with_info[f'decreasing'] = (self.shp_with_info['total_shareholders'] - self.shp_with_info[f'prev_sh']) < 0
        
        # Prices setup
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
            ret = self.get_stock_return(isin, date, lookback_days)
            if ret is not None:
                returns.append(ret)
        return np.mean(returns) if returns else 0

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

        # 2. SENTIMENT FILTERS
        cut = date - pd.Timedelta(days=120)
        recent = self.shp_with_info[(self.shp_with_info['quarter_date'] >= cut) & (self.shp_with_info['quarter_date'] <= date)].copy()
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()
        if recent.empty: return []

        # LEVEL 1: GROUP SELECTION
        g_metrics = recent.groupby('industry_group').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        g_metrics = g_metrics[g_metrics['tot'] >= 5]
        if g_metrics.empty: return []
        g_metrics['pct'] = g_metrics['dec'] / g_metrics['tot'] * 100
        top_groups = g_metrics.sort_values('pct', ascending=False).head(max(int(len(g_metrics)*0.4), 1))['industry_group'].tolist()
        
        # LEVEL 2: INDUSTRY SELECTION (60% ABS)
        i_metrics = recent[recent['industry_group'].isin(top_groups)].groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
        i_metrics['pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
        i_metrics = i_metrics[i_metrics['tot'] >= 3]
        cand_inds_df = i_metrics[i_metrics['pct'] > 60.0]
        if cand_inds_df.empty: return []
        
        # OPTIONAL: RSNP THRESHOLD FILTER
        rsnp_threshold = getattr(self, 'RSNP_THRESHOLD_FILTER', 0.0)
        eligible_inds = cand_inds_df['industry'].tolist()
        
        if rsnp_threshold > 0:
            rs_date = date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS) # Use same lookback logic as RS? No, RSNP usually uses LAG_DAYS
            # Actually, RSNP calculation in BaseRSNP uses LAG_DAYS. 
            # We should probably define lag here or default to 0 if not present.
            lag = getattr(self, 'LAG_DAYS', 0)
            rsnp_date = date - pd.Timedelta(days=lag)
            
            # Use universe benchmark for RSNP calc if available, else standard
            if hasattr(self, 'universe_bench'):
                 # Get return of the specific universe benchmark (e.g. Top 500)
                end_bench = self.universe_bench[self.universe_bench['date'] <= rsnp_date].iloc[-1]['index_value']
                start_date_bench = rsnp_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
                start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
                bench_ret = (end_bench / start_bench) - 1
            else:
                bench_ret = self.get_bench_ret(rsnp_date, self.RS_LOOKBACK_DAYS)
                
            passed_inds = []
            for ind in eligible_inds:
                rsnp = self.calculate_rsnp(ind, rsnp_date, self.RS_LOOKBACK_DAYS, bench_ret)
                if rsnp >= rsnp_threshold:
                    passed_inds.append(ind)
            eligible_inds = passed_inds
            
        if not eligible_inds: return []

        # LEVEL 3: RELATIVE STRENGTH RANKING
        bench_ret = self.get_bench_ret(date, self.RS_LOOKBACK_DAYS)
        rs_results = []
        for ind in eligible_inds: # Iterate only over eligible
            ind_ret = self.get_industry_ret(ind, date, self.RS_LOOKBACK_DAYS)
            rs = ind_ret - bench_ret
            rs_results.append({'industry': ind, 'rs': rs})
        
        rs_df = pd.DataFrame(rs_results)
        ranked_inds = rs_df.sort_values('rs', ascending=False)['industry'].tolist()
        
        # LEVEL 4: STOCK SELECTION (RESTRICTED TO TOP 1000)
        universe_pool = p_slice[p_slice['isin'].isin(top_1000_isins)].merge(self.industry_df[['isin', 'industry']], on='isin').sort_values('mc', ascending=False)
        
        selected = []
        for ind in ranked_inds:
            # Pick from Top 1000 stocks in this industry
            stocks = universe_pool[universe_pool['industry'] == ind].head(4)['isin'].tolist()
            selected.extend(stocks)
            if len(selected) >= self.NUM_STOCKS: break
        return selected[:self.NUM_STOCKS]

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

    def get_price(self, isin, date):
        if isin not in self.price_dates: return None
        idx = np.searchsorted(self.price_dates[isin], np.datetime64(date), side='right') - 1
        return self.price_values[isin][idx] if idx >= 0 else None

    def run(self):
        # Sync-15 Schedule
        base_dates = pd.date_range('2017-02-01', '2026-02-01', freq='QS-FEB')
        dates = [d + pd.Timedelta(days=14) for d in base_dates if d >= pd.Timestamp('2017-05-01')]
        
        # PARAMETERS
        STCG_RATE = 0.20
        LTCG_RATE = 0.125
        LTCG_EXEMPTION = 125000
        SLIPPAGE = 0.0050 # 0.5% per leg (Exchange + Govt + Impact)
        INTEREST_RATE = 0.05
        INTEREST_TAX = 0.30
        RESERVE_PERCENT = 0.05
        
        # TRACKING
        portfolio = {} # {isin: list of {'qty': q, 'price': p, 'date': d}}
        cash = self.INITIAL_CAPITAL
        equity_curve = []
        ltcg_exemption_used = 0
        current_fy = None
        prev_date = dates[0]

        for i, date in enumerate(dates):
            # 1. FY RESET (LTCG EXEMPTION)
            fy = date.year if date.month >= 4 else date.year - 1
            if fy != current_fy:
                ltcg_exemption_used = 0
                current_fy = fy

            # 2. CASH INTEREST
            if i > 0:
                interest = cash * (INTEREST_RATE * (date - prev_date).days / 365.25) * (1 - INTEREST_TAX)
                cash += interest
            
            # 3. GET SELECTION
            stocks = self.calculate_selection(date)
            
            # 4. SELL-OFF CURRENT POSITIONS (LIQUIDATE EVERYTHING FOR QUARTERLY REBALANCE)
            # This is the most conservative and transparent way to ensure tax is paid
            current_liquid_val = cash
            for isin, lots in portfolio.items():
                p_exit = self.get_price(isin, date)
                if p_exit:
                    for lot in lots:
                        exit_price = p_exit * (1 - SLIPPAGE)
                        entry_price = lot['price'] * (1 + SLIPPAGE)
                        exit_val = lot['qty'] * exit_price
                        entry_val = lot['qty'] * entry_price
                        gain = exit_val - entry_val
                        
                        if gain > 0:
                            holding_days = (date - lot['date']).days
                            if holding_days >= 365:
                                # LTCG
                                taxable_gain = max(0, gain - (LTCG_EXEMPTION - ltcg_exemption_used))
                                ltcg_exemption_used += (gain - taxable_gain)
                                tax = taxable_gain * LTCG_RATE
                            else:
                                # STCG
                                tax = gain * STCG_RATE
                            exit_val -= tax
                        current_liquid_val += exit_val
            
            # 5. EXECUTE NEW PORTFOLIO (95% Deployment)
            portfolio = {}
            cash = current_liquid_val
            
            if stocks:
                num_to_buy = len(stocks)
                target_per_stock = (cash * (1 - RESERVE_PERCENT)) / num_to_buy
                
                for isin in stocks:
                    p = self.get_price(isin, date)
                    if p:
                        # Round down shares
                        qty = int(target_per_stock / (p * (1 + SLIPPAGE)))
                        if qty > 0:
                            actual_cost = qty * p * (1 + SLIPPAGE)
                            portfolio[isin] = [{'qty': qty, 'price': p, 'date': date}]
                            cash -= actual_cost
            
            # 6. EQUITY RECORDING
            invested_val = sum([sum([lot['qty'] * (self.get_price(isin, date) or 0) for lot in lots]) 
                               for isin, lots in portfolio.items()])
            val = cash + invested_val
            equity_curve.append({'date': date, 'value': val})
            print(f"[{date.date()}] Net Net Value: ₹{val:,.0f} | Ratio: {invested_val/val:.1%} | Stocks: {len(portfolio)}")
            prev_date = date

        # 7. PERFORMANCE REPORT
        res = pd.DataFrame(equity_curve)
        if not res.empty:
            total_ret = (res.iloc[-1]['value'] / self.INITIAL_CAPITAL - 1) * 100
            print(f"\nFINAL NET NET RETURN: {total_ret:.2f}%")
            
            # Save results
            out_p = self.base_path / 'strategies' / 'outputs' / 'net_net'
            out_p.mkdir(parents=True, exist_ok=True)
            res.to_csv(out_p / f"{self.__class__.__name__}_net_net.csv", index=False)
        
        return res

if __name__ == "__main__":
    Hierarchical40Group60AbsoluteRSTop1000().run()

if __name__ == "__main__":
    Hierarchical40Group60AbsoluteRSTop1000().run()
