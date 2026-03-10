#!/usr/bin/env python
"""
Create Daily Point-in-Time Industry Benchmarks

Generates equal-weighted industry indices that:
- Rebalance quarterly (aligned with shareholding data)
- Use only stocks that existed at each rebalancing date
- Calculate DAILY returns for finer granularity
- Avoid survivorship bias

Output: analysis/outputs/benchmarks/industries/
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class DailyIndustryBenchmarkBuilder:
    """Build daily point-in-time industry benchmarks"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        self.output_path = base_path / 'analysis' / 'outputs' / 'benchmarks' / 'industries'
        
        print("="*80)
        print("DAILY INDUSTRY BENCHMARK BUILDER")
        print("="*80)
        
        self._load_data()
    
    def _load_data(self):
        """Load required database files"""
        print("\nLoading database files...")
        
        # Industry classifications
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'company_name', 'industry', 'industry_group']
        )
        
        # Filter valid industries
        self.industry_df = self.industry_df[
            (self.industry_df['industry'].notna()) &
            (self.industry_df['industry'] != 'Not Available')
        ]
        
        # Stock statistics (for quality filtering)
        self.stats_df = pd.read_csv(
            self.database_path / 'stock_statistics.csv',
            usecols=['isin', 'total_price_records', 'price_start_date', 
                     'price_end_date', 'quality_score']
        )
        self.stats_df['price_start_date'] = pd.to_datetime(self.stats_df['price_start_date'])
        self.stats_df['price_end_date'] = pd.to_datetime(self.stats_df['price_end_date'])
        
        # Create stats lookup
        print("  Creating stats lookup index...")
        self.stats_df = self.stats_df.drop_duplicates('isin')
        self.stats_by_isin = self.stats_df.set_index('isin').to_dict('index')
        
        # Price data
        print("  Loading price data (this may take a moment)...")
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close'],
            dtype={'close': 'float32'}
        )
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        # Create price lookup
        print("  Creating price lookup index...")
        self.price_by_isin = {isin: group.set_index('date')['close'] for isin, group in self.price_df.groupby('isin')}
        
        print(f"  ✅ Loaded:")
        print(f"     - {self.industry_df['industry'].nunique()} industries")
        print(f"     - {len(self.industry_df):,} stock-industry mappings")
        print(f"     - {len(self.price_df):,} price records")
        print(f"     - {len(self.price_by_isin):,} stocks indexed")
        
        self.max_date = self.price_df['date'].max()
        print(f"     - Data available up to: {self.max_date.date()}")
    
    def get_rebalancing_dates(self, start_date='2016-03-31'):
        """Generate quarterly rebalancing dates up to latest data"""
        # Generate quarter ends
        dates = pd.date_range(start=start_date, end=self.max_date, freq='QE')
        dates = list(dates)
        
        # Ensure start date is included if not generated (unlikely with QE but safe)
        if not dates or dates[0] > pd.Timestamp(start_date):
            dates.insert(0, pd.Timestamp(start_date))
            
        # Append latest date if not covered
        if dates[-1] < self.max_date:
            dates.append(self.max_date)
            
        return dates
    
    def get_constituents_at_date(self, industry, as_of_date, min_history_days=90):
        """Get stocks in an industry that existed at a specific date."""
        industry_stocks = self.industry_df[
            self.industry_df['industry'] == industry
        ]['isin'].unique()
        
        valid_constituents = []
        
        for isin in industry_stocks:
            stock_stats = self.stats_by_isin.get(isin)
            
            if not stock_stats:
                continue
            
            # Must have started trading before as_of_date
            if stock_stats['price_start_date'] > as_of_date:
                continue
            
            # Must have ended after as_of_date (or still trading)
            if stock_stats['price_end_date'] < as_of_date:
                continue
            
            # Check if has enough history
            history_days = (as_of_date - stock_stats['price_start_date']).days
            if history_days < min_history_days:
                continue
            
            # Check if has recent price (within 30 days)
            if isin in self.price_by_isin:
                # Optimized check using index search
                prices = self.price_by_isin[isin]
                window_start = as_of_date - timedelta(days=30)
                
                # Check for any price in window [window_start, as_of_date]
                has_price = not prices[window_start:as_of_date].empty
                
                if has_price:
                    valid_constituents.append(isin)
        
        return valid_constituents
    
    def build_industry_benchmark(self, industry):
        """Build daily benchmark timeseries for one industry."""
        rebal_dates = self.get_rebalancing_dates()
        final_index_series = pd.Series(dtype=float)
        current_base_value = 100.0
        
        # Iterate through quarterly periods
        for i, rebal_date in enumerate(rebal_dates[:-1]):
            next_rebal_date = rebal_dates[i + 1]
            
            # Identify constituents for this quarter
            constituents = self.get_constituents_at_date(industry, rebal_date)
            
            if len(constituents) < 3:
                # If insufficient data, flatline or simple carry over (here we just skip/break or handle gaps)
                # Ideally we want continuous series. If gap, we assume return = 0 (cash)
                # But for simplicity, we continue from last value if we have gaps
                idx_dates = pd.date_range(rebal_date, next_rebal_date, freq='D')[1:]
                gap_series = pd.Series(current_base_value, index=idx_dates)
                final_index_series = pd.concat([final_index_series, gap_series])
                continue
            
            # Collect price series for this quarter
            quarter_prices = {}
            for isin in constituents:
                if isin in self.price_by_isin:
                    # Get prices from rebal_date to next_rebal_date
                    # We need rebal_date for base price
                    series = self.price_by_isin[isin][rebal_date:next_rebal_date]
                    # Ensure no duplicates in index
                    series = series[~series.index.duplicated(keep='last')]
                    if not series.empty:
                        quarter_prices[isin] = series
            
            if not quarter_prices:
                # Handle gap matches
                idx_dates = pd.date_range(rebal_date, next_rebal_date, freq='D')[1:]
                gap_series = pd.Series(current_base_value, index=idx_dates)
                final_index_series = pd.concat([final_index_series, gap_series])
                continue
                
            # Create DataFrame
            q_df = pd.DataFrame(quarter_prices)
            
            # Forward fill missing data within the quarter
            q_df = q_df.ffill(limit=10)
            
            # Need base prices at rebal_date
            # Try to get price exactly at rebal_date, or very closest previous
            # Since q_df starts at rebal_date (slice), the first row might be rebal_date
            # But rebal_date might be weekend.
            
            # Resample to daily to fill calendar days (optional but good for charts)
            # q_df = q_df.resample('D').ffill()
            
            # Retrieve base prices (careful with NaNs at start)
            # We normalize to the first valid price for each stock in this window?
            # No, standard is: Price_t / Price_0. Price_0 must be fixed.
            # If a stock is missing Price_0, it shouldn't be in the index this Q?
            # 'get_constituents' checks for recent price.
            
            # Let's take the first valid price in the window as base (proxy for rebal price)
            base_prices = q_df.iloc[0] 
            
            # Calculate performance relative to start of quarter
            rel_perf = q_df / base_prices
            
            # Intra-quarter "Index" (starts at 1.0)
            # Equal weight means average of relative performances
            quarter_curve = rel_perf.mean(axis=1)
            
            # Scale to current global index value
            scaled_curve = quarter_curve * current_base_value
            
            # Append strictly new dates (after rebal_date)
            # quarter_curve includes rebal_date (value 1.0).
            # We want to append (rebal_date, next_rebal_date]
            
            mask = (scaled_curve.index > rebal_date) & (scaled_curve.index <= next_rebal_date)
            segment = scaled_curve[mask]
            
            if segment.empty:
                 continue
                 
            final_index_series = pd.concat([final_index_series, segment])
            
            # Update base value for next quarter
            current_base_value = segment.iloc[-1]
        
        if final_index_series.empty:
            return pd.DataFrame()

        # Convert to DataFrame
        final_index_series.name = 'index_value'
        benchmark_df = final_index_series.reset_index()
        benchmark_df.columns = ['date', 'index_value']
        
        # Calculate daily returns from index value
        benchmark_df['return'] = benchmark_df['index_value'].pct_change() * 100
        benchmark_df['num_constituents'] = 0 # Placeholder or calculate properly
        
        # Fill num_constituents (approximate, since we processed in blocks)
        # We can just leave it as placeholder since we only use index_value for RS
        
        return benchmark_df
    
    def save_industry_benchmark(self, industry, benchmark_df):
        """Save benchmark data"""
        industry_folder = self.output_path / industry.replace('/', '_').replace(' ', '_')
        industry_folder.mkdir(parents=True, exist_ok=True)
        
        timeseries_path = industry_folder / 'timeseries.csv'
        benchmark_df.to_csv(timeseries_path, index=False)
        print(f"    Saved to: {timeseries_path}")

    def build_all_industries(self, max_workers=10):
        """Build benchmarks for all industries in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_industries = sorted(self.industry_df['industry'].unique())
        print(f"\nFound {len(all_industries)} industries to process")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ind = {executor.submit(self.build_industry_benchmark, ind): ind for ind in all_industries}
            
            for i, future in enumerate(as_completed(future_to_ind), 1):
                industry = future_to_ind[future]
                try:
                    df = future.result()
                    if df is not None and len(df) > 0:
                        self.save_industry_benchmark(industry, df)
                        if i % 20 == 0 or i == len(all_industries):
                            print(f"[{i}/{len(all_industries)}] Finished {industry}: {len(df)} records")
                except Exception as e:
                    print(f"[{i}/{len(all_industries)}] Error for {industry}: {e}")

def main():
    try:
        builder = DailyIndustryBenchmarkBuilder()
        builder.build_all_industries(max_workers=10)
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    main()
