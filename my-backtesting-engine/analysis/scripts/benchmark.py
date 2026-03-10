#!/usr/bin/env python
"""
Benchmark Index Generator
Creates an equal-weighted benchmark of top N stocks by market cap
Rebalances monthly
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import sys

class BenchmarkIndex:
    """
    Creates and tracks an equal-weighted benchmark index
    Constituents: Top N stocks by market cap (monthly rebalance)
    Weighting: Equal weight (1/N for each stock)
    """
    
    def __init__(
        self,
        top_n: int = 500,
        initial_value: float = 1000.0,
        database_path: str = "database"
    ):
        """
        Initialize benchmark
        
        Args:
            top_n: Number of top stocks to include (default 500)
            initial_value: Starting index value (default 1000)
            database_path: Path to database folder
        """
        self.top_n = top_n
        self.initial_value = initial_value
        self.database_path = Path(database_path)
        
        # Load required data
        self._load_data()
        
    def _load_data(self):
        """Load price data and outstanding shares"""
        print("Loading data for benchmark calculation...")
        
        # Load outstanding shares
        shares_file = self.database_path / "outstanding_shares.csv"
        if not shares_file.exists():
            raise FileNotFoundError(
                f"Outstanding shares file not found. Run: python scripts/create_outstanding_shares_file.py"
            )
        
        shares_df = pd.read_csv(shares_file)
        self.shares_lookup = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
        
        # Load price data
        print("  Loading price data...")
        price_df = pd.read_csv(
            self.database_path / "price_data.csv",
            usecols=['isin', 'date', 'close'],
            dtype={'isin': 'category', 'close': 'float32'},
            parse_dates=['date']
        )
        
        # Handle duplicates - keep last record for each (isin, date) combination
        duplicates_count = price_df.duplicated(subset=['isin', 'date']).sum()
        if duplicates_count > 0:
            print(f"  Found {duplicates_count:,} duplicate records, keeping last value for each date...")
            price_df = price_df.drop_duplicates(subset=['isin', 'date'], keep='last')
        
        # Map outstanding shares and calculate market cap
        price_df['shares'] = price_df['isin'].map(self.shares_lookup)
        price_df.dropna(subset=['shares'], inplace=True)
        price_df['market_cap'] = price_df['close'] * price_df['shares']
        
        # Sort for efficient queries
        price_df.sort_values(['date', 'isin'], inplace=True)
        
        self.price_data = price_df
        self.min_date = price_df['date'].min()
        self.max_date = price_df['date'].max()
        
        print(f"  Data loaded: {len(price_df):,} records from {self.min_date.date()} to {self.max_date.date()}")
    
    def _get_month_end_dates(self, start_date: str, end_date: str) -> List[datetime]:
        """Get all month-end dates in the range"""
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Generate month-end dates
        try:
            month_ends = pd.date_range(start=start, end=end, freq='ME')
        except:
            # Fallback for older pandas
            month_ends = pd.date_range(start=start, end=end, freq='M')
        
        # Find nearest trading day for each month end
        trading_days = []
        for month_end in month_ends:
            # Look for trading day within ±5 days
            for offset in range(6):
                # Try exact date first, then backwards, then forwards
                for date_offset in [0, -offset, offset]:
                    if date_offset == 0 and offset > 0:
                        continue
                    check_date = month_end + pd.Timedelta(days=date_offset)
                    if check_date in self.price_data['date'].values:
                        trading_days.append(check_date)
                        break
                else:
                    continue
                break
        
        return sorted(set(trading_days))
    
    def _get_top_stocks(self, date: pd.Timestamp) -> pd.DataFrame:
        """Get top N stocks by market cap on a specific date"""
        # Get data for this date
        day_data = self.price_data[self.price_data['date'] == date].copy()
        
        if len(day_data) < self.top_n:
            print(f"Warning: Only {len(day_data)} stocks available on {date.date()}, needed {self.top_n}")
        
        # Get top N by market cap
        top_stocks = day_data.nlargest(min(self.top_n, len(day_data)), 'market_cap')
        
        # Calculate equal weights
        num_stocks = len(top_stocks)
        equal_weight = 1.0 / num_stocks
        top_stocks['weight'] = equal_weight
        
        return top_stocks[['isin', 'close', 'market_cap', 'weight']]
    
    def calculate_benchmark(
        self,
        start_date: str,
        end_date: str,
        rebalance_frequency: str = 'monthly'
    ) -> pd.DataFrame:
        """
        Calculate benchmark index values over time
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            rebalance_frequency: 'monthly' (only monthly supported currently)
            
        Returns:
            DataFrame with daily index values
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Get rebalance dates (month ends)
        rebalance_dates = self._get_month_end_dates(start_date, end_date)
        print(f"\nCalculating equal-weighted benchmark with {len(rebalance_dates)} monthly rebalances...")
        print(f"Each stock will have {100/self.top_n:.3f}% weight ({self.top_n} stocks)")
        
        # Get all trading days in range
        all_dates = self.price_data[
            (self.price_data['date'] >= start) & 
            (self.price_data['date'] <= end)
        ]['date'].unique()
        all_dates = sorted(all_dates)
        
        if not all_dates:
            print("No trading days found in date range")
            return pd.DataFrame()
        
        # Initialize tracking
        index_values = []
        current_index = self.initial_value
        
        # Track holdings for each rebalance period
        period_holdings = {}
        period_start_index = self.initial_value
        rebalance_idx = 0
        
        for i, date in enumerate(all_dates):
            # Check if rebalance needed
            is_rebalance = (rebalance_idx < len(rebalance_dates) and 
                           date >= rebalance_dates[rebalance_idx])
            
            if is_rebalance or i == 0:
                # Get new holdings (top N stocks by market cap)
                top_stocks = self._get_top_stocks(date)
                
                # Store holdings with base prices for this period
                period_holdings = {}
                for _, row in top_stocks.iterrows():
                    period_holdings[row['isin']] = {
                        'weight': row['weight'],  # Equal weight
                        'base_price': row['close']
                    }
                
                # Reset period tracking
                period_start_index = current_index
                
                if i > 0:
                    rebalance_idx += 1
                    print(f"  Rebalanced on {date.date()}: {len(period_holdings)} stocks @ {period_holdings[list(period_holdings.keys())[0]]['weight']*100:.3f}% each")
            
            # Calculate index value based on equal-weighted returns
            if period_holdings:
                # Get today's prices
                today_prices = self.price_data[self.price_data['date'] == date]
                today_prices = today_prices.set_index('isin')['close']
                
                # Calculate equal-weighted return from period start
                total_return = 0.0
                valid_stocks = 0
                
                for isin, holding in period_holdings.items():
                    if isin in today_prices.index:
                        # Stock return since rebalance
                        stock_return = (today_prices[isin] / holding['base_price']) - 1
                        # Add with equal weight
                        total_return += stock_return * holding['weight']
                        valid_stocks += 1
                
                # Calculate index value
                # Index = Period Start Index * (1 + Equal Weighted Return)
                current_index = period_start_index * (1 + total_return)
            
            index_values.append({
                'date': date,
                'index_value': current_index,
                'num_stocks': len(period_holdings)
            })
            
            # Progress indicator
            if i % 100 == 0 or i == len(all_dates) - 1:
                sys.stdout.write(f"\rProgress: {i+1}/{len(all_dates)} days")
                sys.stdout.flush()
        
        print("\n")
        
        # Create DataFrame
        result = pd.DataFrame(index_values)
        
        # Add calculated metrics
        result['daily_return'] = result['index_value'].pct_change()
        result['cumulative_return'] = (result['index_value'] / self.initial_value - 1) * 100
        
        return result


def create_benchmark(
    top_n: int = 500,
    start_date: str = "2020-01-01",
    end_date: str = "2026-01-28",
    output_dir: str = "analysis/outputs/benchmarks"
) -> pd.DataFrame:
    """
    Create and save equal-weighted benchmark index
    
    Args:
        top_n: Number of top stocks by market cap (default 500)
        start_date: Start date
        end_date: End date
        output_dir: Output directory
        
    Returns:
        DataFrame with benchmark data
    """
    # Create benchmark
    benchmark = BenchmarkIndex(top_n=top_n)
    
    # Calculate
    result = benchmark.calculate_benchmark(start_date, end_date)
    
    if result.empty:
        print("Error: No benchmark data generated")
        return result
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = output_path / f"benchmark_top{top_n}_equal_weight_{start_date}_to_{end_date}.csv"
    result.to_csv(filename, index=False)
    
    # Calculate additional statistics
    total_return = result['cumulative_return'].iloc[-1]
    years = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days / 365.25
    cagr = ((result['index_value'].iloc[-1] / benchmark.initial_value) ** (1/years) - 1) * 100
    
    # Volatility (annualized)
    daily_vol = result['daily_return'].std()
    annual_vol = daily_vol * np.sqrt(252) * 100
    
    # Max drawdown
    cummax = result['index_value'].cummax()
    drawdown = (result['index_value'] - cummax) / cummax * 100
    max_drawdown = drawdown.min()
    
    # Print summary
    print("\n" + "="*80)
    print(f"EQUAL-WEIGHTED BENCHMARK: Top {top_n} Stocks (Monthly Rebalance)")
    print("="*80)
    print(f"Period: {start_date} to {end_date} ({years:.1f} years)")
    print(f"Weight per Stock: {100/top_n:.3f}%")
    print(f"\nInitial Index Value: {benchmark.initial_value:,.2f}")
    print(f"Final Index Value: {result['index_value'].iloc[-1]:,.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"CAGR: {cagr:.2f}%")
    print(f"Annualized Volatility: {annual_vol:.2f}%")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Sharpe Ratio: {(cagr / annual_vol):.2f}" if annual_vol > 0 else "N/A")
    print(f"\nTotal Trading Days: {len(result):,}")
    print(f"Average # of Stocks: {result['num_stocks'].mean():.0f}")
    print(f"\nBenchmark saved to: {filename}")
    print("="*80)
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create Equal-Weighted Benchmark Index")
    parser.add_argument('--top-n', type=int, default=500, help='Number of top stocks by market cap (default 500)')
    parser.add_argument('--start-date', type=str, default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2026-01-28', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str, default='analysis/outputs/benchmarks', help='Output directory')
    
    args = parser.parse_args()
    
    create_benchmark(
        top_n=args.top_n,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir
    )
