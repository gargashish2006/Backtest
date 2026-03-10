#!/usr/bin/env python
"""
Industry Group Shareholder Analysis - Top 1000 Stocks by Market Cap
Multi-Period (2Q, 1Y, 2Y, 5Y)

Analyzes which industry GROUPS are gaining/losing shareholders across different time horizons,
focusing ONLY on the top 1000 stocks by market capitalization for cleaner signals.

Time horizons:
- 2 Quarters (6 months)
- 1 Year (4 quarters)
- 2 Years (8 quarters)
- 5 Years (20 quarters)
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Top1000IndustryGroupAnalyzer:
    """Analyze industry group shareholder changes for top 1000 stocks by market cap"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        # Define periods
        self.periods = {
            '2Q (6M)': 2,
            '1Y': 4,
            '2Y': 8,
            '5Y': 20
        }
        
        print("Loading data...")
        self._load_data()
    
    def _load_data(self):
        """Load required data"""
        # Shareholding patterns
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv'
        )
        
        # Industry info (using industry_group)
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'industry_group']
        )
        
        # Price data for market cap calculation
        print("  Loading price data...")
        price_chunks = []
        for chunk in pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close'],
            chunksize=500000
        ):
            price_chunks.append(chunk)
        
        self.price_df = pd.concat(price_chunks, ignore_index=True)
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"Loaded {len(self.industry_df):,} industry mappings")
        print(f"Loaded {len(self.price_df):,} price records")
    
    def _parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings to quarter-end dates"""
        try:
            if 'Q' in str(quarter_str) and 'FY' in str(quarter_str):
                parts = quarter_str.split()
                quarter_num = int(parts[0].replace('Q', ''))
                fy_year = int(parts[1].replace('FY', ''))
                
                quarter_end_months = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}
                month, day = quarter_end_months[quarter_num]
                
                if quarter_num == 4:
                    year = fy_year
                else:
                    year = fy_year - 1
                
                return pd.Timestamp(year=year, month=month, day=day)
            else:
                return pd.to_datetime(quarter_str)
        except Exception as e:
            return None
    
    def calculate_top_1000_stocks(self):
        """Calculate top 1000 stocks by market cap as of latest available quarter"""
        print("\nCalculating top 1000 stocks by market cap...")
        
        # Get latest quarter with substantial data
        shp_temp = self.shareholding_df.copy()
        shp_temp['quarter_date'] = shp_temp['quarter'].apply(self._parse_quarter_to_date)
        shp_temp = shp_temp.dropna(subset=['quarter_date'])
        
        quarter_counts = shp_temp.groupby('quarter_date').size()
        substantial_quarters = quarter_counts[quarter_counts >= 1000].index
        latest_quarter = substantial_quarters.max()
        
        print(f"  Using quarter: {latest_quarter.date()}")
        
        # Get price on that quarter end date
        price_window = self.price_df[
            (self.price_df['date'] >= latest_quarter - pd.Timedelta(days=7)) &
            (self.price_df['date'] <= latest_quarter + pd.Timedelta(days=7))
        ].copy()
        
        latest_prices = price_window.sort_values('date').groupby('isin').last().reset_index()
        latest_prices = latest_prices[['isin', 'close']].rename(columns={'close': 'price'})
        
        print(f"  Found prices for {len(latest_prices):,} stocks")
        
        # Get outstanding shares from shareholding data for that quarter
        shp_quarter = shp_temp[shp_temp['quarter_date'] == latest_quarter][['isin', 'total_outstanding_shares']].copy()
        shp_quarter = shp_quarter.dropna(subset=['total_outstanding_shares'])
        shp_quarter = shp_quarter.rename(columns={'total_outstanding_shares': 'outstanding_shares'})
        
        print(f"  Found outstanding shares for {len(shp_quarter):,} stocks")
        
        # Calculate market cap
        market_caps = latest_prices.merge(shp_quarter, on='isin', how='inner')
        market_caps['market_cap'] = market_caps['price'] * market_caps['outstanding_shares']
        
        # Get top 1000
        top_1000 = market_caps.nlargest(1000, 'market_cap')
        
        print(f"  ✅ Identified top 1000 stocks by market cap")
        print(f"  Market cap range: ₹{top_1000['market_cap'].min()/1e7:.0f}Cr to ₹{top_1000['market_cap'].max()/1e7:.0f}Cr")
        
        self.top_1000_isins = set(top_1000['isin'])
        self.market_caps = market_caps
        
        return top_1000
    
    def prepare_data(self):
        """Prepare data with industry group mapping and filter for top 1000"""
        print("\nPreparing data...")
        
        # Calculate top 1000 first
        self.calculate_top_1000_stocks()
        
        # Merge with industry group
        df = self.shareholding_df.merge(
            self.industry_df,
            on='isin',
            how='left'
        )
        
        # Filter for top 1000 stocks
        df = df[df['isin'].isin(self.top_1000_isins)].copy()
        print(f"  Filtered to top 1000: {len(df):,} records")
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        df['quarter_date'] = df['quarter'].apply(self._parse_quarter_to_date)
        
        # Remove invalid data
        df = df.dropna(subset=['quarter_date', 'total_shareholders', 'industry_group'])
        df = df[df['total_shareholders'] > 0]
        df = df[df['industry_group'] != 'Not Available']
        
        # Sort
        df = df.sort_values(['isin', 'quarter_date'])
        
        print(f"  Valid records: {len(df):,}")
        print(f"  Industry Groups: {df['industry_group'].nunique()}")
        print(f"  Unique stocks: {df['isin'].nunique()}")
        print(f"  Date range: {df['quarter_date'].min().date()} to {df['quarter_date'].max().date()}")
        
        self.prepared_df = df
        
        return df
    
    def analyze_period(self, quarters_back):
        """Analyze shareholder changes for a specific lookback period"""
        print(f"\n  Analyzing {quarters_back}-quarter lookback...")
        
        df = self.prepared_df.copy()
        
        # Calculate shareholders N quarters ago
        df[f'shareholders_{quarters_back}q_ago'] = df.groupby('isin')['total_shareholders'].shift(quarters_back)
        df[f'change_{quarters_back}q'] = df['total_shareholders'] - df[f'shareholders_{quarters_back}q_ago']
        df[f'is_increase_{quarters_back}q'] = df[f'change_{quarters_back}q'] > 0
        
        # Get latest quarter with substantial data
        quarter_counts = df.groupby('quarter_date').size()
        substantial_quarters = quarter_counts[quarter_counts >= 500].index  # Lower threshold for top 1000
        
        if len(substantial_quarters) == 0:
            print(f"    ⚠️ No quarters with sufficient data")
            return None
        
        latest_quarter = substantial_quarters.max()
        latest_data = df[df['quarter_date'] == latest_quarter].copy()
        
        # Remove stocks without lookback data
        latest_data = latest_data.dropna(subset=[f'shareholders_{quarters_back}q_ago'])
        
        if len(latest_data) == 0:
            print(f"    ⚠️ No data available for {quarters_back}Q lookback")
            return None
        
        # Calculate by industry group
        group_stats = latest_data.groupby('industry_group').agg({
            'isin': 'count',
            f'is_increase_{quarters_back}q': ['sum', 'mean'],
            f'change_{quarters_back}q': ['mean', 'median']
        }).round(4)
        
        # Flatten column names
        group_stats.columns = ['num_stocks', 'num_increasing', 'pct_increasing', 'avg_change', 'median_change']
        group_stats['pct_increasing'] = group_stats['pct_increasing'] * 100
        
        # Sort by percentage increasing
        group_stats = group_stats.sort_values('pct_increasing', ascending=False)
        
        # Filter out groups with too few stocks
        group_stats = group_stats[group_stats['num_stocks'] >= 3]
        
        print(f"    ✅ Analyzed {len(group_stats)} industry groups")
        print(f"    Latest quarter: {latest_quarter.date()}")
        print(f"    Stocks with data: {len(latest_data)}")
        
        return group_stats
    
    def analyze_all_periods(self):
        """Analyze all time periods"""
        print("\n" + "="*80)
        print("ANALYZING ALL TIME PERIODS (TOP 1000 STOCKS)")
        print("="*80)
        
        results = {}
        
        for period_name, quarters_back in self.periods.items():
            print(f"\n{period_name} ({quarters_back} quarters back):")
            stats = self.analyze_period(quarters_back)
            if stats is not None:
                results[period_name] = stats
        
        self.period_results = results
        return results
    
    def print_rankings(self, n=10):
        """Print formatted rankings for all periods"""
        print("\n" + "="*80)
        print("INDUSTRY GROUP RANKINGS - TOP 1000 STOCKS BY MARKET CAP")
        print("="*80)
        
        for period_name in self.periods.keys():
            if period_name not in self.period_results:
                continue
            
            stats = self.period_results[period_name]
            
            print(f"\n{'='*80}")
            print(f"📊 {period_name} LOOKBACK")
            print(f"{'='*80}")
            
            # Adjust n if fewer groups available
            actual_n = min(n, len(stats))
            
            # Top groups
            print(f"\n🟢 TOP {actual_n} INDUSTRY GROUPS - Gaining Shareholders ({period_name})")
            print("-"*80)
            top = stats.head(actual_n)
            
            for i, (group, row) in enumerate(top.iterrows(), 1):
                print(f"{i:2d}. {group:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):4d} stocks")
            
            # Bottom groups
            print(f"\n🔴 BOTTOM {actual_n} INDUSTRY GROUPS - Losing Shareholders ({period_name})")
            print("-"*80)
            bottom = stats.tail(actual_n)[::-1]
            
            for i, (group, row) in enumerate(bottom.iterrows(), 1):
                print(f"{i:2d}. {group:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):4d} stocks")
    
    def identify_consistent_performers(self, threshold=60):
        """Identify industry groups with consistent strong growth across all periods"""
        print(f"\n🎯 Identifying consistent performers (>{threshold}% across all periods)...")
        
        if not self.period_results or len(self.period_results) == 0:
            print("  ⚠️ No period results available")
            return pd.DataFrame()
        
        first_period = list(self.period_results.keys())[0]
        
        comparison_data = []
        for group in self.period_results[first_period].index:
            row = {'Industry_Group': group}
            all_periods_above_threshold = True
            
            for period_name, stats in self.period_results.items():
                if group in stats.index:
                    pct = stats.loc[group, 'pct_increasing']
                    row[period_name] = pct
                    if pct < threshold:
                        all_periods_above_threshold = False
                else:
                    all_periods_above_threshold = False
            
            row['Consistent'] = all_periods_above_threshold
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) == 0:
            print("  ⚠️ No industry groups to compare")
            return pd.DataFrame()
        
        consistent = comparison_df[comparison_df['Consistent'] == True].copy()
        
        if len(consistent) > 0:
            consistent['Avg'] = consistent[list(self.periods.keys())].mean(axis=1)
            consistent = consistent.sort_values('Avg', ascending=False)
        
            print(f"\n✅ Found {len(consistent)} industry groups with consistent strong growth:")
            print("-"*80)
            
            for idx, (_, row) in enumerate(consistent.iterrows(), 1):
                print(f"{idx:2d}. {row['Industry_Group']:45s} | Avg: {row['Avg']:5.1f}%")
                for period in self.periods.keys():
                    print(f"    {period:8s}: {row[period]:5.1f}%")
        else:
            print(f"\n⚠️ No industry groups found with >{threshold}% across ALL periods")
        
        return consistent
    
    def save_results(self):
        """Save all results to CSV files"""
        print("\n💾 Saving results...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to save")
            return None
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        # Save each period separately
        for period_name, stats in self.period_results.items():
            period_clean = period_name.replace(' ', '_').replace('(', '').replace(')', '')
            filename = f'top1000_industry_group_{period_clean}_{timestamp}.csv'
            output_path = output_dir / filename
            stats.to_csv(output_path)
            print(f"  ✅ Saved: {filename}")
        
        # Save combined comparison
        first_period = list(self.period_results.keys())[0]
        comparison_data = []
        
        for group in self.period_results[first_period].index:
            row = {'Industry_Group': group}
            num_stocks = None
            
            for period_name, stats in self.period_results.items():
                if group in stats.index:
                    row[f'{period_name}_pct'] = stats.loc[group, 'pct_increasing']
                    if num_stocks is None:
                        num_stocks = stats.loc[group, 'num_stocks']
            
            row['num_stocks'] = num_stocks
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) > 0:
            first_period_col = f'{first_period}_pct'
            if first_period_col in comparison_df.columns:
                comparison_df = comparison_df.sort_values(first_period_col, ascending=False)
        
        combined_path = output_dir / f'top1000_industry_group_all_periods_{timestamp}.csv'
        comparison_df.to_csv(combined_path, index=False)
        print(f"  ✅ Saved combined: top1000_industry_group_all_periods_{timestamp}.csv")
        
        return combined_path


def main():
    print("="*80)
    print("INDUSTRY GROUP ANALYSIS - TOP 1000 STOCKS BY MARKET CAP")
    print("Multi-Period: 2 Quarters (6M), 1 Year, 2 Years, 5 Years")
    print("="*80)
    
    analyzer = Top1000IndustryGroupAnalyzer()
    
    # Prepare data (includes top 1000 calculation)
    analyzer.prepare_data()
    
    # Analyze all periods
    results = analyzer.analyze_all_periods()
    
    if not results or len(results) == 0:
        print("\n⚠️ No analysis results generated. Check data availability.")
        return analyzer
    
    # Print rankings
    analyzer.print_rankings(n=10)
    
    # Identify consistent performers
    consistent = analyzer.identify_consistent_performers(threshold=60)
    
    # Save results
    analyzer.save_results()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nKey Differences from Full Universe:")
    print("  - Focuses on top 1000 stocks by market capitalization")
    print("  - Removes small-cap noise and illiquid stocks")
    print("  - Better signals for institutional/large investors")
    print("  - More tradeable and liquid universe")
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
