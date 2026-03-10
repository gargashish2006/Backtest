#!/usr/bin/env python
"""
Market Breadth Analysis - Stocks Above 200-Day Moving Average

This script calculates the percentage of stocks trading above their 200-day moving average
for the top 100 and top 1000 stocks by market capitalization.

The analysis is done on a rolling basis where:
- Market cap rankings are recalculated for each date
- Only stocks with sufficient price history (200+ days) are included
- Results show market breadth over time

Usage:
    python analysis/market_breadth_analysis.py --start-date 2020-01-01 --end-date 2026-01-31
    python analysis/market_breadth_analysis.py --date 2026-01-31  # Single date
    python analysis/market_breadth_analysis.py --latest  # Most recent date
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
from typing import Tuple, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.scripts import MarketCapCalculator, TechnicalIndicators


class MarketBreadthAnalyzer:
    """
    Analyze market breadth by calculating percentage of stocks above 200-day MA.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the market breadth analyzer.
        
        Args:
            base_path: Base path to the backtesting engine directory
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
            
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        # Initialize calculators
        self.market_cap_calc = MarketCapCalculator(base_path)
        self.indicators = TechnicalIndicators()
        
        # Load data
        print("Loading price data...")
        self.price_data = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date']
        )
        print(f"Loaded {len(self.price_data):,} price records")
        
        # Load outstanding shares
        self.outstanding_shares = pd.read_csv(
            self.database_path / 'outstanding_shares.csv'
        )
        
    def get_top_stocks_by_market_cap(
        self,
        date: str,
        top_n: int = 100
    ) -> pd.DataFrame:
        """
        Get top N stocks by market cap on a specific date.
        
        Args:
            date: Date in 'YYYY-MM-DD' format
            top_n: Number of top stocks to return (default: 100)
            
        Returns:
            DataFrame with columns: isin, symbol, company_name, market_cap_cr
        """
        date_dt = pd.to_datetime(date)
        
        # Get prices for this date
        prices_on_date = self.price_data[
            self.price_data['date'] == date_dt
        ][['isin', 'close']].copy()
        
        if prices_on_date.empty:
            return pd.DataFrame()
        
        # Merge with outstanding shares
        market_caps = self.outstanding_shares.merge(
            prices_on_date,
            on='isin',
            how='inner'
        )
        
        # Calculate market cap
        market_caps['market_cap_cr'] = (
            market_caps['close'] * market_caps['total_outstanding_shares'] / 10_000_000
        )
        
        # Use primary symbol (NSE if available, else BSE)
        market_caps['symbol'] = market_caps['nse_symbol'].fillna(
            market_caps['bse_code'].astype('Int64').astype(str)
        )
        
        # Sort by market cap and get top N
        top_stocks = market_caps.nlargest(top_n, 'market_cap_cr')
        
        return top_stocks[['isin', 'symbol', 'company_name', 'market_cap_cr']]
    
    def calculate_stocks_above_ma(
        self,
        date: str,
        top_n: int = 100,
        ma_period: int = 200
    ) -> Tuple[float, int, int, pd.DataFrame]:
        """
        Calculate percentage of top N stocks above their moving average.
        
        Args:
            date: Date in 'YYYY-MM-DD' format
            top_n: Number of top stocks by market cap (default: 100)
            ma_period: Moving average period in days (default: 200)
            
        Returns:
            Tuple of (percentage, stocks_above, total_stocks, details_df)
        """
        # Get top stocks by market cap on this date
        top_stocks = self.get_top_stocks_by_market_cap(date, top_n)
        
        if top_stocks.empty:
            return 0.0, 0, 0, pd.DataFrame()
        
        date_dt = pd.to_datetime(date)
        
        # For each stock, check if it's above its MA
        results = []
        
        for _, stock in top_stocks.iterrows():
            isin = stock['isin']
            
            # Get price history up to this date (need at least ma_period days)
            stock_prices = self.price_data[
                (self.price_data['isin'] == isin) &
                (self.price_data['date'] <= date_dt)
            ].sort_values('date').tail(ma_period + 50)  # Extra buffer
            
            if len(stock_prices) < ma_period:
                # Not enough data - skip this stock
                continue
            
            # Calculate MA
            stock_prices = stock_prices.copy()
            stock_prices['ma'] = stock_prices['close'].rolling(window=ma_period).mean()
            
            # Get the values for the specific date
            date_data = stock_prices[stock_prices['date'] == date_dt]
            
            if date_data.empty:
                continue
            
            current_price = date_data.iloc[0]['close']
            current_ma = date_data.iloc[0]['ma']
            
            if pd.isna(current_ma):
                continue
            
            above_ma = current_price > current_ma
            pct_from_ma = ((current_price - current_ma) / current_ma) * 100
            
            results.append({
                'isin': isin,
                'symbol': stock['symbol'],
                'company_name': stock['company_name'],
                'market_cap_cr': stock['market_cap_cr'],
                'price': current_price,
                'ma': current_ma,
                'above_ma': above_ma,
                'pct_from_ma': pct_from_ma
            })
        
        if not results:
            return 0.0, 0, 0, pd.DataFrame()
        
        results_df = pd.DataFrame(results)
        
        stocks_above = results_df['above_ma'].sum()
        total_stocks = len(results_df)
        percentage = (stocks_above / total_stocks) * 100
        
        return percentage, stocks_above, total_stocks, results_df
    
    def analyze_date_range(
        self,
        start_date: str,
        end_date: str,
        top_n_list: list = [100, 1000],
        ma_period: int = 200,
        frequency: str = 'daily'
    ) -> pd.DataFrame:
        """
        Analyze market breadth over a date range.
        
        Args:
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            top_n_list: List of top N values to analyze (default: [100, 1000])
            ma_period: Moving average period (default: 200)
            frequency: 'daily', 'weekly', or 'monthly' (default: 'daily')
            
        Returns:
            DataFrame with breadth analysis over time
        """
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Get unique trading dates in the range
        trading_dates = self.price_data[
            (self.price_data['date'] >= start_dt) &
            (self.price_data['date'] <= end_dt)
        ]['date'].unique()
        trading_dates = pd.Series(trading_dates).sort_values()
        
        # Apply frequency filter
        if frequency == 'weekly':
            # Use last trading day of each week
            trading_dates = pd.to_datetime(trading_dates)
            trading_dates = trading_dates.to_frame(name='date')
            trading_dates['week'] = trading_dates['date'].dt.to_period('W')
            trading_dates = trading_dates.groupby('week')['date'].max()
        elif frequency == 'monthly':
            # Use last trading day of each month
            trading_dates = pd.to_datetime(trading_dates)
            trading_dates = trading_dates.to_frame(name='date')
            trading_dates['month'] = trading_dates['date'].dt.to_period('M')
            trading_dates = trading_dates.groupby('month')['date'].max()
        
        results = []
        total_dates = len(trading_dates)
        
        print(f"\nAnalyzing {total_dates} dates from {start_date} to {end_date}")
        print(f"Market cap groups: {top_n_list}")
        print(f"Moving average period: {ma_period} days")
        print(f"Frequency: {frequency}")
        print("-" * 80)
        
        for idx, date in enumerate(trading_dates, 1):
            if isinstance(date, pd.Timestamp):
                date_str = date.strftime('%Y-%m-%d')
            else:
                date_str = str(date)
            
            if idx % 10 == 0 or idx == total_dates:
                print(f"Processing {idx}/{total_dates}: {date_str}", end='\r')
            
            row = {'date': date_str}
            
            for top_n in top_n_list:
                pct, above, total, _ = self.calculate_stocks_above_ma(
                    date_str, top_n, ma_period
                )
                
                row[f'top_{top_n}_pct_above_ma'] = pct
                row[f'top_{top_n}_stocks_above'] = above
                row[f'top_{top_n}_total_stocks'] = total
            
            results.append(row)
        
        print()  # New line after progress
        
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def analyze_single_date(
        self,
        date: str,
        top_n_list: list = [100, 1000],
        ma_period: int = 200,
        verbose: bool = True
    ) -> dict:
        """
        Detailed analysis for a single date.
        
        Args:
            date: Date in 'YYYY-MM-DD' format
            top_n_list: List of top N values to analyze
            ma_period: Moving average period
            verbose: Print detailed results
            
        Returns:
            Dictionary with analysis results
        """
        results = {'date': date, 'groups': {}}
        
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"Market Breadth Analysis - {date}")
            print(f"{'=' * 80}")
        
        for top_n in top_n_list:
            pct, above, total, details = self.calculate_stocks_above_ma(
                date, top_n, ma_period
            )
            
            results['groups'][f'top_{top_n}'] = {
                'percentage': pct,
                'stocks_above': above,
                'total_stocks': total,
                'details': details
            }
            
            if verbose:
                print(f"\nTop {top_n} Stocks by Market Cap:")
                print(f"  Stocks Above {ma_period}-Day MA: {above}/{total} ({pct:.1f}%)")
                
                if not details.empty:
                    avg_distance = details['pct_from_ma'].mean()
                    print(f"  Average Distance from MA: {avg_distance:+.2f}%")
                    
                    # Show top 5 above and below MA
                    above_stocks = details[details['above_ma']].nlargest(5, 'pct_from_ma')
                    below_stocks = details[~details['above_ma']].nsmallest(5, 'pct_from_ma')
                    
                    if not above_stocks.empty:
                        print(f"\n  Top 5 Stocks Above MA:")
                        for _, row in above_stocks.iterrows():
                            print(f"    {row['company_name']:30s} {row['symbol']:15s} {row['pct_from_ma']:+6.2f}%")
                    
                    if not below_stocks.empty:
                        print(f"\n  Top 5 Stocks Below MA:")
                        for _, row in below_stocks.iterrows():
                            print(f"    {row['company_name']:30s} {row['symbol']:15s} {row['pct_from_ma']:+6.2f}%")
        
        if verbose:
            print(f"\n{'=' * 80}")
        
        return results


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Analyze market breadth - stocks above 200-day MA'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='Single date to analyze (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for range analysis (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for range analysis (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Analyze the most recent date'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        nargs='+',
        default=[100, 1000],
        help='List of top N stocks to analyze (default: 100 1000)'
    )
    parser.add_argument(
        '--ma-period',
        type=int,
        default=200,
        help='Moving average period in days (default: 200)'
    )
    parser.add_argument(
        '--frequency',
        type=str,
        choices=['daily', 'weekly', 'monthly'],
        default='daily',
        help='Analysis frequency for date range (default: daily)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file path for range analysis'
    )
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = MarketBreadthAnalyzer()
    
    # Determine what to analyze
    if args.latest:
        # Get most recent date
        latest_date = analyzer.price_data['date'].max()
        date = latest_date.strftime('%Y-%m-%d')
        print(f"Using latest available date: {date}")
        results = analyzer.analyze_single_date(date, args.top_n, args.ma_period)
        
    elif args.date:
        # Single date analysis
        results = analyzer.analyze_single_date(args.date, args.top_n, args.ma_period)
        
    elif args.start_date and args.end_date:
        # Date range analysis
        results_df = analyzer.analyze_date_range(
            args.start_date,
            args.end_date,
            args.top_n,
            args.ma_period,
            args.frequency
        )
        
        # Display summary
        print(f"\n{'=' * 80}")
        print("Summary Statistics")
        print(f"{'=' * 80}")
        print(results_df.describe())
        
        # Save to CSV if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            results_df.to_csv(output_path, index=False)
            print(f"\n✅ Results saved to: {output_path}")
        else:
            # Default output path
            output_dir = Path(__file__).parent / 'outputs' / 'reports'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f'market_breadth_{args.start_date}_to_{args.end_date}.csv'
            results_df.to_csv(output_file, index=False)
            print(f"\n✅ Results saved to: {output_file}")
    else:
        parser.print_help()
        print("\nError: Please specify either --latest, --date, or both --start-date and --end-date")
        sys.exit(1)


if __name__ == '__main__':
    main()
