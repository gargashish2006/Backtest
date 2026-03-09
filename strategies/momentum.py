import pandas as pd
import numpy as np
from datetime import datetime
from data.data_handler import DataHandler

class MomentumStrategy:
    """Selects top 15 stocks by 1-year return with M-Cap and Liquidity filters."""
    def __init__(self, data_handler: DataHandler, num_stocks: int = 15, lag_days: int = 7):
        self.dh = data_handler
        self.universe_size = 1000
        self.liquidity_threshold_pct = 0.00005 # 0.005% = 0.00005
        self.num_stocks = num_stocks
        self.lag_days = lag_days
        self.lookback_days = 365

    def calculate_selection(self, date: pd.Timestamp) -> pd.DataFrame:
        """Runs the strategy logic for a given date."""
        # 0. Apply calculation lag
        calc_date = date - pd.Timedelta(days=self.lag_days)
        
        # 1. Get Universe (Top 1000 by M-Cap)
        metrics = self.dh.get_daily_metrics(calc_date)
        if metrics.empty:
            all_dates = self.dh.get_all_dates()
            valid_dates = [d for d in all_dates if d <= calc_date]
            if not valid_dates: return []
            calc_date = max(valid_dates)
            metrics = self.dh.get_daily_metrics(calc_date)
            
        if metrics.empty: return []
        
        top_1000 = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        eligible_isins = top_1000['isin'].tolist()
        
        # 2. Liquidity Filter (Min Traded Val > 0.005% of M-Cap in last 21 trading days)
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
        
        if not passed_liquidity: return []

        # 3. Momentum Signal (1-year return, 1 week lag)
        signal_date = date - pd.Timedelta(days=self.lag_days)
        base_date = signal_date - pd.Timedelta(days=self.lookback_days)
        
        # Get prices at signal_date and base_date
        # We'll find the closest available trading dates
        all_dates = self.dh.get_all_dates()
        
        try:
            actual_signal_date = max([d for d in all_dates if d <= signal_date])
            actual_base_date = max([d for d in all_dates if d <= base_date])
        except ValueError:
            return []

        p_signal = self.dh.get_daily_prices(actual_signal_date)
        p_base = self.dh.get_daily_prices(actual_base_date)
        
        returns = []
        for isin in passed_liquidity:
            p1 = p_signal.get(isin)
            p0 = p_base.get(isin)
            if p1 and p0 and p0 > 0:
                ret = (p1 / p0) - 1
                returns.append({'isin': isin, 'momentum': ret})
        
        if not returns: return []
        
        # 4. Final Selection
        ret_df = pd.DataFrame(returns)
        selection = ret_df.sort_values('momentum', ascending=False).head(self.num_stocks)
        isins = selection['isin'].tolist()
        
        # Return weights (equal weight 1/N)
        weight = 1.0 / len(isins) if isins else 0
        return {isin: weight for isin in isins}
