import pandas as pd
from typing import Dict, List
from data.data_handler import DataHandler

class IndustryMomentumRSNPStrategy:
    """Ranks industries by % of stocks outperforming the Top 1000 Benchmark."""
    def __init__(self, data_handler: DataHandler, num_stocks: int = 15, max_per_industry: int = 3, lag_days: int = 7, rsnp_threshold: float = 0.33):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.lag_days = lag_days
        self.rsnp_threshold = rsnp_threshold
        self.lookback_days = 365
        self.universe_size = 1000
        self.liquidity_threshold_pct = 0.00005 # 0.005%

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns target weights (isin -> weight)."""
        # 0. Apply calculation lag
        calc_date = date - pd.Timedelta(days=self.lag_days)
        
        metrics = self.dh.get_daily_metrics(calc_date)
        if metrics.empty: 
            # Fallback to closest available data before calc_date if needed
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
        
        # 5. Determine Benchmark 1000 1-yr return
        bench_df = self.dh.top_1000_bench
        p_bench_end = bench_df[bench_df['date'] <= calc_date]['index_value'].iloc[-1]
        lookback_start = calc_date - pd.Timedelta(days=self.lookback_days)
        p_bench_start = bench_df[bench_df['date'] <= lookback_start]['index_value'].iloc[-1]
        bench_return = (p_bench_end / p_bench_start) - 1
        
        # 6. Calculate Top 1000 Performance vs Benchmark
        all_dates = self.dh.get_all_dates()
        actual_end_date = max([d for d in all_dates if d <= calc_date])
        actual_start_date = max([d for d in all_dates if d <= lookback_start])
        
        p_end_map = self.dh.get_daily_prices(actual_end_date)
        p_start_map = self.dh.get_daily_prices(actual_start_date)
        
        stock_returns = []
        for isin in passed_liquidity:
            p1 = p_end_map.get(isin)
            p0 = p_start_map.get(isin)
            if p1 and p0 and p0 > 0:
                ret = (p1 / p0) - 1
                stock_returns.append({'isin': isin, 'return': ret})
        
        if not stock_returns: return {}
        
        ret_df = pd.DataFrame(stock_returns)
        ret_df['industry'] = ret_df['isin'].map(self.dh.isin_to_industry)
        ret_df['is_winner'] = ret_df['return'] > bench_return
        
        # 7. Rank Industries by % Winners
        ind_stats = ret_df.groupby('industry')['is_winner'].agg(['mean', 'count']).reset_index()
        ind_stats = ind_stats.rename(columns={'mean': 'win_rate'})
        
        # New: Filter by RSNP threshold
        ind_stats = ind_stats[ind_stats['win_rate'] > self.rsnp_threshold]
        ind_stats = ind_stats.sort_values(['win_rate', 'count'], ascending=False)
        
        # 8. Select Stocks from Top Industries
        selected_isins = []
        for _, row in ind_stats.iterrows():
            industry = row['industry']
            # Get stocks in this industry from the Top 1000 pool, sorted by M-Cap
            ind_stocks = stock_data[stock_data['industry'] == industry].sort_values('mc', ascending=False)
            
            picks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for isin in picks:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                if len(selected_isins) >= self.num_stocks:
                    break
            
            if len(selected_isins) >= self.num_stocks:
                break
                
        if not selected_isins: return {}
        
        # New: Use fixed weight based on num_stocks to leave remaining as cash
        weight_per_stock = 1.0 / self.num_stocks
        return {isin: weight_per_stock for isin in selected_isins}
