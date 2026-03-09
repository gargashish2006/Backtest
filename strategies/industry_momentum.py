import pandas as pd
from typing import Dict, List
from data.data_handler import DataHandler

class IndustryMomentumStrategy:
    """Ranks industries by 1-year return and picks top M-Cap stocks within them."""
    def __init__(self, data_handler: DataHandler, num_stocks: int = 15, max_per_industry: int = 4, lag_days: int = 7):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.lag_days = lag_days
        self.lookback_days = 365
        self.universe_size = 1000
        self.liquidity_threshold_pct = 0.00005 # 0.005%

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns target weights (isin -> weight)."""
        # 0. Apply calculation lag
        calc_date = date - pd.Timedelta(days=self.lag_days)
        
        metrics = self.dh.get_daily_metrics(calc_date)
        if metrics.empty:
            # Fallback to closest available data before calc_date
            all_dates = self.dh.get_all_dates()
            valid_dates = [d for d in all_dates if d <= calc_date]
            if not valid_dates: return {}
            calc_date = max(valid_dates)
            metrics = self.dh.get_daily_metrics(calc_date)
            
        if metrics.empty: return {}
        
        # 1. Map all stocks to industry
        metrics['industry'] = metrics['isin'].map(self.dh.isin_to_industry)
        
        # 2. Filter Industries with at least 4 stocks (applied INITIALLY)
        counts = metrics.groupby('industry').size()
        robust_industries = counts[counts >= 4].index.tolist()
        robust_metrics = metrics[metrics['industry'].isin(robust_industries)].copy()
        
        # 3. Get Universe (Top 1000 by M-Cap from robust industries)
        top_1000 = robust_metrics.sort_values('mc', ascending=False).head(self.universe_size)
        eligible_isins = top_1000['isin'].tolist()
        
        # 4. Liquidity Filter (Min Traded Val > 0.005% of M-Cap in last 21 trading days)
        all_dates = self.dh.get_all_dates()
        trading_dates = [d for d in all_dates if d <= calc_date]
        if len(trading_dates) < 21:
            start_date = trading_dates[0]
        else:
            start_date = trading_dates[-21]
            
        hist_data = self.dh.price_df[(self.dh.price_df['date'] <= calc_date) & 
                                     (self.dh.price_df['date'] >= start_date) &
                                     (self.dh.price_df['isin'].isin(eligible_isins))]
        
        min_liquidity = hist_data.groupby('isin')['traded_val'].min().reset_index()
        
        liquidity_check = pd.merge(min_liquidity, top_1000[['isin', 'mc']], on='isin')
        liquidity_check['threshold'] = liquidity_check['mc'] * self.liquidity_threshold_pct
        passed_liquidity = liquidity_check[liquidity_check['traded_val'] >= liquidity_check['threshold']]['isin'].tolist()
        
        if not passed_liquidity: return {}
        
        stock_data = top_1000[top_1000['isin'].isin(passed_liquidity)].copy()
        
        # 5. Rank Industries by 1-year Return
        active_industries = stock_data['industry'].dropna().unique()
        industry_returns = []
        lookback_start = calc_date - pd.Timedelta(days=self.lookback_days)
        
        for ind in active_industries:
            p_end = self.dh.get_industry_benchmark_price(ind, calc_date)
            p_start = self.dh.get_industry_benchmark_price(ind, lookback_start)
            
            if p_start > 0:
                ret = (p_end / p_start) - 1
                industry_returns.append({'industry': ind, 'return': ret})
        
        if not industry_returns: return {}
        
        ind_rank = pd.DataFrame(industry_returns).sort_values('return', ascending=False)
        
        # 5. Select Stocks
        selected_isins = []
        for _, row in ind_rank.iterrows():
            industry = row['industry']
            # Get stocks in this industry, sorted by M-Cap
            ind_stocks = stock_data[stock_data['industry'] == industry].sort_values('mc', ascending=False)
            
            # Take top 4
            picks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for isin in picks:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                
                if len(selected_isins) >= self.num_stocks:
                    break
            
            if len(selected_isins) >= self.num_stocks:
                break
        
        # 4. Equal Weight Allocation
        if not selected_isins: return {}
        weight = 1.0 / len(selected_isins)
        return {isin: weight for isin in selected_isins}
