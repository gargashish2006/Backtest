"""
Ultra-Optimized Market Breadth Analysis
Calculates percentage of stocks above 200-day MA for Top 100 and Top 1000 companies.
Optimizations:
1. Pre-calculates Market Cap and MA status globally (Vectorized).
2. Loads only essential columns to save memory.
3. Uses nlargest for fast ranking.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
import time
import sys

class MarketBreadthAnalyzer:
    def __init__(self, database_path: str = "database"):
        """Initialize with path to database"""
        self.database_path = Path(database_path)
        self.shares_lookup = {}
        self.price_data = None
        
        # Load data immediately
        self._load_data()
        
    def _load_data(self):
        """Load and prepare all data with global vectorization"""
        start_time = time.time()
        print("Loading and optimizing data...")
        
        # 1. Load Outstanding Shares
        shares_df = pd.read_csv(self.database_path / "outstanding_shares.csv")
        # Create a mapping series for fast merging
        self.shares_map = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
        
        # 2. Load Price Data (Only essential columns)
        # Using specified optimized types
        dtype_spec = {
            'isin': 'category',
            'close': 'float32',
            # 'date' will be parsed
        }
        
        price_df = pd.read_csv(
            self.database_path / "price_data.csv",
            usecols=['isin', 'date', 'close'],
            dtype=dtype_spec,
            parse_dates=['date']
        )
        
        print(f"  Data loaded in {time.time() - start_time:.2f}s. Rows: {len(price_df):,}")
        
        # 3. Calculate 200-day Moving Average (Vectorized)
        print("  Calculating 200-day Moving Averages...")
        # Sort is required for rolling window
        price_df.sort_values(['isin', 'date'], inplace=True)
        
        # Groupby rolling calculation
        # transform is efficient here. 
        # min_periods=1 ensures we get some MA even if <200 days exist, 
        # but standard is min_periods=200. Let's use 200.
        price_df['ma_200'] = price_df.groupby('isin', observed=True)['close'].transform(
            lambda x: x.rolling(window=200, min_periods=200).mean()
        )
        
        # 4. Pre-calculate "Above MA" status
        # Boolean column (True/False/NaN)
        price_df['above_ma'] = price_df['close'] > price_df['ma_200']
        
        # Optimized DataFrame stored in memory
        self.price_data = price_df
        
        # Get available date range
        self.min_date = price_df['date'].min()
        self.max_date = price_df['date'].max()
        
        print(f"  Optimization Complete. Date Range: {self.min_date.date()} to {self.max_date.date()}")
        print(f"  Total Initialization Time: {time.time() - start_time:.2f}s")
        print("-" * 60)

    def _calculate_market_caps_for_dates(self, dates):
        """Calculate market caps only for specific dates to save memory/compute"""
        # Filter for relevant dates first
        subset = self.price_data[self.price_data['date'].isin(dates)].copy()
        
        # Map shares
        subset['shares'] = subset['isin'].map(self.shares_map)
        
        # Calculate Cap
        subset['market_cap'] = subset['close'] * subset['shares']
        
        return subset

    def analyze_date(self, target_date: str, pre_calculated_subset=None):
        """Analyze a specific date. If pre_calculated_subset provided, use it."""
        target_date = pd.to_datetime(target_date)
        
        if pre_calculated_subset is not None:
            # Use the efficient subset
            day_data = pre_calculated_subset[pre_calculated_subset['date'] == target_date]
        else:
            # Fallback for single date query
            day_data = self.price_data[self.price_data['date'] == target_date].copy()
            day_data['shares'] = day_data['isin'].map(self.shares_map)
            day_data['market_cap'] = day_data['close'] * day_data['shares']

        if len(day_data) == 0:
            return None
        
        # Top 100/1000 - nlargest is faster than sort
        # Note: 'market_cap' might have NaNs (if no shares data), drop them
        valid_data = day_data.dropna(subset=['market_cap'])
        
        # We need top 1000, so let's get that slice
        top_1000_data = valid_data.nlargest(1000, 'market_cap')
        
        # Ensure we only count stocks that have a valid MA (to match previous logic)
        top_1000_data = top_1000_data.dropna(subset=['ma_200'])

        # Top 100 is just the first 100 of Top 1000
        top_100_data = top_1000_data.head(100)
        
        # Calculate stats (vectorized sum of boolean)
        stats = {
            'date': target_date.date().isoformat(),
            'top_100_total': len(top_100_data),
            'top_100_above_ma': top_100_data['above_ma'].sum(),
            'top_1000_total': len(top_1000_data),
            'top_1000_above_ma': top_1000_data['above_ma'].sum(),
        }
        
        # Percentages
        stats['top_100_pct'] = (stats['top_100_above_ma'] / stats['top_100_total'] * 100) if stats['top_100_total'] > 0 else 0
        stats['top_1000_pct'] = (stats['top_1000_above_ma'] / stats['top_1000_total'] * 100) if stats['top_1000_total'] > 0 else 0
        
        return stats

    def analyze_range(self, start_date, end_date, frequency='monthly'):
        """Analyze a date range efficiently"""
        dates = pd.date_range(start=start_date, end=end_date, freq=self._get_freq_alias(frequency))
        print(f"Analyzing {len(dates)} dates in range ({frequency})...")
        
        # Batch optimization: Calculate Market Caps only for these dates
        print("  Batch processing market caps for target dates...")
        relevant_data = self._calculate_market_caps_for_dates(dates)
        
        results = []
        for date in dates:
            # Pass the pre-calculated subset
            res = self.analyze_date(date, pre_calculated_subset=relevant_data)
            if res:
                results.append(res)
                
        return pd.DataFrame(results)

    def _get_freq_alias(self, frequency):
        """Convert friendly frequency name to Pandas alias"""
        display_map = {
            'daily': 'B',  # Business day
            'weekly': 'W-FRI', # Weekly, ending Friday
            'monthly': 'ME'   # Month End
        }
        return display_map.get(frequency, 'B')

def main():
    parser = argparse.ArgumentParser(description='Ultra-Optimized Market Breadth Analysis')
    parser.add_argument('--start-date', required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--frequency', default='monthly', choices=['daily', 'weekly', 'monthly'])
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ULTRA-OPTIMIZED MARKET BREADTH ANALYSIS")
    print("=" * 60)
    
    analyzer = MarketBreadthAnalyzer()
    
    start_time = time.time()
    results = analyzer.analyze_range(args.start_date, args.end_date, args.frequency)
    duration = time.time() - start_time
    
    print("\nAnalysis Results (Sample):")
    print(results.tail())
    
    print("\nSummary Statistics:")
    print("-" * 30)
    print(f"Total Dates Analyzed: {len(results)}")
    print(f"Average Top 100 > 200DMA: {results['top_100_pct'].mean():.2f}%")
    print(f"Average Top 1000 > 200DMA: {results['top_1000_pct'].mean():.2f}%")
    print("-" * 30)
    print(f"Analysis Duration: {duration:.4f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    main()
