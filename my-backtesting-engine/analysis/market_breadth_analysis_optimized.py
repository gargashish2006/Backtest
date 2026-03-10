#!/usr/bin/env python
"""
Optimized Market Breadth Analysis

Calculates the percentage of stocks above their 200-day moving average
for the top 100 and top 1000 stocks by market cap.

Optimization strategies:
1. Pre-calculate market caps for all dates at once
2. Use vectorized operations for moving averages
3. Batch process stocks instead of one-by-one
4. Cache intermediate results
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.scripts import MarketCapCalculator


class OptimizedMarketBreadthAnalyzer:
    """Optimized analyzer for market breadth metrics"""
    
    def __init__(self, base_path=None):
        """Initialize the analyzer"""
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading data...")
        # Load all data at once
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date'],
            usecols=['isin', 'date', 'close']
        )
        
        self.outstanding_shares = pd.read_csv(
            self.database_path / 'outstanding_shares.csv'
        )
        
        # Create ISIN to symbol mapping
        self.isin_to_symbol = dict(zip(
            self.outstanding_shares['isin'],
            self.outstanding_shares['nse_symbol'].fillna(
                self.outstanding_shares['bse_code'].astype('Int64').astype(str)
            )
        ))
        
        self.isin_to_company = dict(zip(
            self.outstanding_shares['isin'],
            self.outstanding_shares['company_name']
        ))
        
        print(f"Loaded {len(self.price_df):,} price records for {self.price_df['isin'].nunique():,} stocks")
        
    def calculate_market_caps_bulk(self, dates=None):
        """
        Pre-calculate market caps for all stocks across all dates.
        
        Args:
            dates: Optional list of dates to calculate for. If None, uses all dates.
        
        Returns:
            DataFrame with columns: date, isin, price, market_cap_cr
        """
        print("Calculating market caps for all dates...")
        
        # Filter for specific dates if provided
        if dates is not None:
            price_subset = self.price_df[self.price_df['date'].isin(dates)].copy()
        else:
            price_subset = self.price_df.copy()
        
        # Merge with outstanding shares
        market_caps = price_subset.merge(
            self.outstanding_shares[['isin', 'total_outstanding_shares']],
            on='isin',
            how='inner'
        )
        
        # Calculate market cap in Crores
        market_caps['market_cap_cr'] = (
            market_caps['close'] * market_caps['total_outstanding_shares'] / 10_000_000
        )
        
        # Keep only needed columns
        market_caps = market_caps[['date', 'isin', 'close', 'market_cap_cr']]
        
        print(f"Calculated market caps for {len(market_caps):,} date-stock combinations")
        
        return market_caps
    
    def calculate_moving_averages_bulk(self, window=200):
        """
        Calculate moving averages for all stocks at once using vectorized operations.
        
        Args:
            window: Moving average window (default: 200 days)
        
        Returns:
            DataFrame with columns: date, isin, close, ma_200
        """
        print(f"Calculating {window}-day moving averages...")
        
        # Sort by isin and date for proper rolling calculation
        sorted_df = self.price_df.sort_values(['isin', 'date']).copy()
        
        # Calculate moving average for each stock using groupby
        sorted_df['ma_200'] = sorted_df.groupby('isin')['close'].transform(
            lambda x: x.rolling(window=window, min_periods=window).mean()
        )
        
        # Remove rows where MA couldn't be calculated (not enough data)
        ma_df = sorted_df.dropna(subset=['ma_200'])
        
        print(f"Calculated MAs for {ma_df['isin'].nunique():,} stocks")
        
        return ma_df
    
    def get_top_n_stocks_by_market_cap(self, market_caps_df, date, n=100):
        """
        Get top N stocks by market cap for a specific date.
        
        Args:
            market_caps_df: Pre-calculated market caps DataFrame
            date: Date to get top stocks for
            n: Number of top stocks to return
        
        Returns:
            List of ISINs for top N stocks
        """
        date_data = market_caps_df[market_caps_df['date'] == date]
        top_n = date_data.nlargest(n, 'market_cap_cr')
        return top_n['isin'].tolist()
    
    def calculate_breadth_for_date(self, date, market_caps_df, ma_df, top_100_isins, top_1000_isins):
        """
        Calculate market breadth for a specific date.
        
        Args:
            date: Date to calculate for
            market_caps_df: Pre-calculated market caps
            ma_df: Pre-calculated moving averages
            top_100_isins: List of top 100 stock ISINs for this date
            top_1000_isins: List of top 1000 stock ISINs for this date
        
        Returns:
            Dictionary with breadth metrics
        """
        # Get MA data for this date
        date_ma = ma_df[ma_df['date'] == date]
        
        # Calculate for top 100
        top_100_data = date_ma[date_ma['isin'].isin(top_100_isins)]
        above_ma_100 = (top_100_data['close'] > top_100_data['ma_200']).sum()
        total_100 = len(top_100_data)
        pct_100 = (above_ma_100 / total_100 * 100) if total_100 > 0 else 0
        
        # Calculate for top 1000
        top_1000_data = date_ma[date_ma['isin'].isin(top_1000_isins)]
        above_ma_1000 = (top_1000_data['close'] > top_1000_data['ma_200']).sum()
        total_1000 = len(top_1000_data)
        pct_1000 = (above_ma_1000 / total_1000 * 100) if total_1000 > 0 else 0
        
        return {
            'date': date,
            'top_100_above_ma': above_ma_100,
            'top_100_total': total_100,
            'top_100_pct': pct_100,
            'top_1000_above_ma': above_ma_1000,
            'top_1000_total': total_1000,
            'top_1000_pct': pct_1000
        }
    
    def analyze_date_range(self, start_date, end_date, frequency='weekly'):
        """
        Analyze market breadth over a date range.
        
        Args:
            start_date: Start date (string 'YYYY-MM-DD' or datetime)
            end_date: End date (string 'YYYY-MM-DD' or datetime)
            frequency: 'daily', 'weekly', or 'monthly'
        
        Returns:
            DataFrame with breadth metrics over time
        """
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        print(f"\nAnalyzing market breadth from {start_date.date()} to {end_date.date()}")
        print(f"Frequency: {frequency}")
        
        # Get all trading dates in range
        all_dates = self.price_df[
            (self.price_df['date'] >= start_date) &
            (self.price_df['date'] <= end_date)
        ]['date'].unique()
        all_dates = sorted(all_dates)
        
        # Sample dates based on frequency
        if frequency == 'daily':
            analysis_dates = all_dates
        elif frequency == 'weekly':
            # Take first trading day of each week
            analysis_dates = pd.to_datetime(all_dates).to_series()
            analysis_dates = analysis_dates.groupby(
                [analysis_dates.dt.year, analysis_dates.dt.isocalendar().week]
            ).first().values
        elif frequency == 'monthly':
            # Take first trading day of each month
            analysis_dates = pd.to_datetime(all_dates).to_series()
            analysis_dates = analysis_dates.groupby(
                [analysis_dates.dt.year, analysis_dates.dt.month]
            ).first().values
        else:
            raise ValueError(f"Invalid frequency: {frequency}. Use 'daily', 'weekly', or 'monthly'")
        
        print(f"Analyzing {len(analysis_dates)} dates...")
        
        # Pre-calculate market caps for all analysis dates
        market_caps_df = self.calculate_market_caps_bulk(dates=analysis_dates)
        
        # Pre-calculate moving averages for all stocks
        ma_df = self.calculate_moving_averages_bulk(window=200)
        
        # Filter MA data to only analysis dates
        ma_df = ma_df[ma_df['date'].isin(analysis_dates)]
        
        # Calculate breadth for each date
        results = []
        for i, date in enumerate(analysis_dates, 1):
            date_ts = pd.Timestamp(date)  # Convert numpy datetime64 to pandas Timestamp
            if i % 10 == 0:
                print(f"  Processing date {i}/{len(analysis_dates)}: {date_ts.date()}")
            
            # Get top stocks for this date
            top_100_isins = self.get_top_n_stocks_by_market_cap(market_caps_df, date_ts, n=100)
            top_1000_isins = self.get_top_n_stocks_by_market_cap(market_caps_df, date_ts, n=1000)
            
            # Calculate breadth
            breadth = self.calculate_breadth_for_date(
                date_ts, market_caps_df, ma_df, top_100_isins, top_1000_isins
            )
            results.append(breadth)
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        results_df['date'] = pd.to_datetime(results_df['date'])
        results_df = results_df.sort_values('date')
        
        return results_df
    
    def analyze_single_date(self, date):
        """
        Analyze market breadth for a single date.
        
        Args:
            date: Date to analyze (string 'YYYY-MM-DD' or datetime)
        
        Returns:
            Dictionary with breadth metrics
        """
        date = pd.to_datetime(date)
        
        print(f"\nAnalyzing market breadth for {date.date()}")
        
        # Calculate market caps for this date
        market_caps_df = self.calculate_market_caps_bulk(dates=[date])
        
        # Calculate moving averages
        ma_df = self.calculate_moving_averages_bulk(window=200)
        ma_df = ma_df[ma_df['date'] == date]
        
        # Get top stocks
        top_100_isins = self.get_top_n_stocks_by_market_cap(market_caps_df, date, n=100)
        top_1000_isins = self.get_top_n_stocks_by_market_cap(market_caps_df, date, n=1000)
        
        # Calculate breadth
        breadth = self.calculate_breadth_for_date(
            date, market_caps_df, ma_df, top_100_isins, top_1000_isins
        )
        
        return breadth
    
    def save_results(self, results_df, filename):
        """Save results to CSV"""
        output_path = self.base_path / 'analysis' / 'outputs' / 'reports' / filename
        results_df.to_csv(output_path, index=False)
        print(f"\n✅ Results saved to: {output_path}")
        return output_path


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimized Market Breadth Analysis')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--date', type=str, help='Single date to analyze (YYYY-MM-DD)')
    parser.add_argument('--frequency', type=str, default='weekly',
                       choices=['daily', 'weekly', 'monthly'],
                       help='Analysis frequency for date ranges')
    parser.add_argument('--output', type=str, help='Output filename (optional)')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = OptimizedMarketBreadthAnalyzer()
    
    if args.date:
        # Single date analysis
        result = analyzer.analyze_single_date(args.date)
        
        print("\n" + "=" * 80)
        print("MARKET BREADTH ANALYSIS")
        print("=" * 80)
        print(f"Date: {result['date'].date()}")
        print()
        print(f"Top 100 Stocks by Market Cap:")
        print(f"  Above 200-day MA: {result['top_100_above_ma']}/{result['top_100_total']} ({result['top_100_pct']:.1f}%)")
        print()
        print(f"Top 1000 Stocks by Market Cap:")
        print(f"  Above 200-day MA: {result['top_1000_above_ma']}/{result['top_1000_total']} ({result['top_1000_pct']:.1f}%)")
        print("=" * 80)
        
    elif args.start_date and args.end_date:
        # Date range analysis
        results_df = analyzer.analyze_date_range(
            args.start_date,
            args.end_date,
            frequency=args.frequency
        )
        
        # Display summary
        print("\n" + "=" * 80)
        print("MARKET BREADTH ANALYSIS - SUMMARY")
        print("=" * 80)
        print(f"Period: {args.start_date} to {args.end_date}")
        print(f"Analysis dates: {len(results_df)}")
        print()
        print("Top 100 Stocks:")
        print(f"  Average % above MA: {results_df['top_100_pct'].mean():.1f}%")
        print(f"  Min: {results_df['top_100_pct'].min():.1f}%")
        print(f"  Max: {results_df['top_100_pct'].max():.1f}%")
        print()
        print("Top 1000 Stocks:")
        print(f"  Average % above MA: {results_df['top_1000_pct'].mean():.1f}%")
        print(f"  Min: {results_df['top_1000_pct'].min():.1f}%")
        print(f"  Max: {results_df['top_1000_pct'].max():.1f}%")
        print()
        
        # Display recent values
        print("Recent Values:")
        print("-" * 80)
        recent = results_df.tail(10)
        for _, row in recent.iterrows():
            print(f"{row['date'].date()}  |  Top 100: {row['top_100_pct']:5.1f}%  |  Top 1000: {row['top_1000_pct']:5.1f}%")
        print("=" * 80)
        
        # Save results
        if args.output:
            filename = args.output
        else:
            filename = f"market_breadth_{args.start_date}_to_{args.end_date}_{args.frequency}.csv"
        
        analyzer.save_results(results_df, filename)
        
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Analyze single date")
        print("  python analysis/market_breadth_analysis_optimized.py --date 2026-01-28")
        print()
        print("  # Analyze date range (weekly)")
        print("  python analysis/market_breadth_analysis_optimized.py --start-date 2025-01-01 --end-date 2026-01-28")
        print()
        print("  # Analyze date range (monthly)")
        print("  python analysis/market_breadth_analysis_optimized.py --start-date 2020-01-01 --end-date 2026-01-28 --frequency monthly")


if __name__ == '__main__':
    main()
