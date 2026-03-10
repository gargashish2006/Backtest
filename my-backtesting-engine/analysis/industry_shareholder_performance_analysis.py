#!/usr/bin/env python
"""
Industry Shareholder & Performance Analysis

Analyzes which industries are gaining/losing shareholders and correlates this
with future 1-year price performance to identify potential outperformers.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class IndustryShareholderAnalyzer:
    """Analyze industry-level shareholder changes and price performance"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading data...")
        self._load_data()
    
    def _load_data(self):
        """Load shareholding, industry, and price data"""
        
        # Load shareholding patterns
        print("  Loading shareholding data...")
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        print(f"  Loaded {len(self.shareholding_df):,} shareholding records")
        
        # Load industry info
        print("  Loading industry classifications...")
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'industry', 'industry_group']
        )
        print(f"  Loaded {len(self.industry_df):,} industry records")
        
        # Load price data (with chunking for efficiency)
        print("  Loading price data (this may take a moment)...")
        price_chunks = []
        for chunk in pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close'],
            chunksize=500000
        ):
            price_chunks.append(chunk)
        
        self.price_df = pd.concat(price_chunks, ignore_index=True)
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        print(f"  Loaded {len(self.price_df):,} price records")
    
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
    
    def calculate_shareholder_changes(self):
        """Calculate 2Q shareholder changes by industry"""
        print("\nCalculating 2Q shareholder changes by industry...")
        
        # Merge shareholding with industry
        shp_with_industry = self.shareholding_df.merge(
            self.industry_df[['isin', 'industry', 'industry_group']],
            on='isin',
            how='left'
        )
        
        # Filter valid industries
        shp_with_industry = shp_with_industry[
            (shp_with_industry['industry'].notna()) &
            (shp_with_industry['industry'] != 'Not Available')
        ].copy()
        
        print(f"  Processing {len(shp_with_industry):,} records with valid industry data")
        
        # Parse quarter dates
        shp_with_industry['quarter_date'] = shp_with_industry['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        valid_data = shp_with_industry.dropna(
            subset=['quarter_date', 'total_shareholders']
        ).copy()
        valid_data = valid_data[valid_data['total_shareholders'] > 0]
        
        # Sort by ISIN and quarter date
        valid_data = valid_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate 2Q changes
        valid_data['shareholders_2q_ago'] = valid_data.groupby('isin')['total_shareholders'].shift(2)
        valid_data['change_2q'] = valid_data['total_shareholders'] - valid_data['shareholders_2q_ago']
        valid_data['pct_change_2q'] = (valid_data['change_2q'] / valid_data['shareholders_2q_ago']) * 100
        
        # Flag increases
        valid_data['is_increase'] = valid_data['change_2q'] > 0
        
        # Group by quarter and industry
        industry_quarterly = valid_data.groupby(['quarter_date', 'industry']).agg({
            'isin': 'count',
            'is_increase': 'sum',
            'change_2q': 'mean',
            'pct_change_2q': 'mean',
            'total_shareholders': 'mean'
        }).reset_index()
        
        industry_quarterly.columns = [
            'quarter_date', 'industry', 'num_stocks', 
            'num_increasing', 'avg_change', 'avg_pct_change', 'avg_shareholders'
        ]
        
        # Calculate percentage increasing
        industry_quarterly['pct_increasing'] = (
            industry_quarterly['num_increasing'] / industry_quarterly['num_stocks']
        ) * 100
        
        print(f"✅ Calculated metrics for {industry_quarterly['industry'].nunique()} industries")
        
        self.industry_quarterly = industry_quarterly
        return valid_data
    
    def calculate_forward_returns(self, shareholder_data):
        """Calculate 1-year forward returns for each stock at each quarter"""
        print("\nCalculating 1-year forward returns...")
        
        # Get unique quarter dates
        unique_quarters = sorted(shareholder_data['quarter_date'].dropna().unique())
        
        results = []
        
        for quarter_date in unique_quarters:
            # Get stocks for this quarter
            quarter_stocks = shareholder_data[
                shareholder_data['quarter_date'] == quarter_date
            ][['isin', 'industry', 'quarter_date', 'change_2q', 'is_increase']].copy()
            
            if len(quarter_stocks) == 0:
                continue
            
            # Define 1-year forward date
            forward_date = quarter_date + pd.DateOffset(years=1)
            
            # Get prices at quarter date
            quarter_prices = self.price_df[
                (self.price_df['date'] >= quarter_date - pd.Timedelta(days=7)) &
                (self.price_df['date'] <= quarter_date + pd.Timedelta(days=7))
            ].copy()
            
            quarter_prices = quarter_prices.sort_values('date').groupby('isin').last().reset_index()
            quarter_prices = quarter_prices[['isin', 'close']].rename(columns={'close': 'price_start'})
            
            # Get prices 1 year forward
            forward_prices = self.price_df[
                (self.price_df['date'] >= forward_date - pd.Timedelta(days=7)) &
                (self.price_df['date'] <= forward_date + pd.Timedelta(days=7))
            ].copy()
            
            forward_prices = forward_prices.sort_values('date').groupby('isin').last().reset_index()
            forward_prices = forward_prices[['isin', 'close']].rename(columns={'close': 'price_end'})
            
            # Merge prices
            stock_returns = quarter_stocks.merge(quarter_prices, on='isin', how='left')
            stock_returns = stock_returns.merge(forward_prices, on='isin', how='left')
            
            # Calculate returns
            stock_returns['return_1y'] = (
                (stock_returns['price_end'] - stock_returns['price_start']) / 
                stock_returns['price_start']
            ) * 100
            
            # Remove invalid returns
            stock_returns = stock_returns[
                (stock_returns['return_1y'].notna()) &
                (stock_returns['return_1y'] > -95) &  # Filter extreme outliers
                (stock_returns['return_1y'] < 500)
            ]
            
            if len(stock_returns) > 0:
                results.append(stock_returns)
        
        if len(results) == 0:
            print("⚠️ No forward returns could be calculated")
            return pd.DataFrame()
        
        forward_returns = pd.concat(results, ignore_index=True)
        print(f"✅ Calculated forward returns for {len(forward_returns):,} stock-quarter observations")
        
        self.forward_returns = forward_returns
        return forward_returns
    
    def analyze_industry_performance(self):
        """Analyze correlation between shareholder growth and future returns"""
        print("\nAnalyzing industry performance correlation...")
        
        if not hasattr(self, 'forward_returns') or len(self.forward_returns) == 0:
            print("⚠️ No forward returns data available")
            return None
        
        # Group by quarter and industry
        industry_performance = self.forward_returns.groupby(['quarter_date', 'industry']).agg({
            'isin': 'count',
            'is_increase': lambda x: (x.sum() / len(x)) * 100,
            'return_1y': 'mean',
            'change_2q': 'mean'
        }).reset_index()
        
        industry_performance.columns = [
            'quarter_date', 'industry', 'num_stocks',
            'pct_shareholders_increasing', 'avg_forward_return', 'avg_shareholder_change'
        ]
        
        # Filter industries with at least 5 stocks
        industry_performance = industry_performance[
            industry_performance['num_stocks'] >= 5
        ]
        
        # Calculate correlation
        correlation = industry_performance.groupby('industry').apply(
            lambda x: x['pct_shareholders_increasing'].corr(x['avg_forward_return'])
            if len(x) > 5 else np.nan
        ).reset_index()
        correlation.columns = ['industry', 'correlation']
        
        # Calculate average metrics by industry
        avg_metrics = industry_performance.groupby('industry').agg({
            'pct_shareholders_increasing': 'mean',
            'avg_forward_return': 'mean',
            'num_stocks': 'sum'
        }).reset_index()
        
        # Merge
        industry_summary = avg_metrics.merge(correlation, on='industry')
        industry_summary = industry_summary.sort_values('correlation', ascending=False)
        
        print(f"✅ Analyzed {len(industry_summary)} industries")
        
        self.industry_summary = industry_summary
        return industry_performance, industry_summary
    
    def get_current_industry_rankings(self):
        """Get current industries ranked by recent shareholder growth"""
        print("\nRanking industries by recent shareholder growth...")
        
        # Get last 4 quarters (1 year)
        recent_quarters = sorted(self.industry_quarterly['quarter_date'].unique())[-4:]
        
        recent_data = self.industry_quarterly[
            self.industry_quarterly['quarter_date'].isin(recent_quarters)
        ]
        
        # Calculate average metrics for recent period
        current_rankings = recent_data.groupby('industry').agg({
            'pct_increasing': 'mean',
            'avg_pct_change': 'mean',
            'num_stocks': 'mean',
            'avg_change': 'mean'
        }).reset_index()
        
        current_rankings = current_rankings[current_rankings['num_stocks'] >= 5]
        current_rankings = current_rankings.sort_values('pct_increasing', ascending=False)
        
        print(f"✅ Ranked {len(current_rankings)} industries")
        
        self.current_rankings = current_rankings
        return current_rankings
    
    def plot_top_bottom_industries(self):
        """Plot top and bottom industries by shareholder growth"""
        
        if not hasattr(self, 'current_rankings'):
            self.get_current_industry_rankings()
        
        # Get top 10 and bottom 10
        top_10 = self.current_rankings.head(10)
        bottom_10 = self.current_rankings.tail(10)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
        
        # Top 10
        colors_top = ['green' if x >= 50 else 'orange' for x in top_10['pct_increasing']]
        ax1.barh(range(len(top_10)), top_10['pct_increasing'], color=colors_top, alpha=0.7)
        ax1.set_yticks(range(len(top_10)))
        ax1.set_yticklabels(top_10['industry'], fontsize=10)
        ax1.axvline(x=50, color='gray', linestyle='--', alpha=0.5, linewidth=1.5)
        ax1.set_xlabel('% Stocks with Increasing Shareholders (2Q)', fontsize=11, fontweight='bold')
        ax1.set_title('Top 10 Industries - Gaining Shareholders', fontsize=12, fontweight='bold', pad=15)
        ax1.grid(True, alpha=0.3, axis='x')
        ax1.invert_yaxis()
        
        # Add values
        for i, (idx, row) in enumerate(top_10.iterrows()):
            ax1.text(row['pct_increasing'] + 1, i, f"{row['pct_increasing']:.1f}%", 
                    va='center', fontsize=9)
        
        # Bottom 10
        colors_bottom = ['red' if x < 50 else 'orange' for x in bottom_10['pct_increasing']]
        ax2.barh(range(len(bottom_10)), bottom_10['pct_increasing'], color=colors_bottom, alpha=0.7)
        ax2.set_yticks(range(len(bottom_10)))
        ax2.set_yticklabels(bottom_10['industry'], fontsize=10)
        ax2.axvline(x=50, color='gray', linestyle='--', alpha=0.5, linewidth=1.5)
        ax2.set_xlabel('% Stocks with Increasing Shareholders (2Q)', fontsize=11, fontweight='bold')
        ax2.set_title('Bottom 10 Industries - Losing Shareholders', fontsize=12, fontweight='bold', pad=15)
        ax2.grid(True, alpha=0.3, axis='x')
        ax2.invert_yaxis()
        
        # Add values
        for i, (idx, row) in enumerate(bottom_10.iterrows()):
            ax2.text(row['pct_increasing'] + 1, i, f"{row['pct_increasing']:.1f}%", 
                    va='center', fontsize=9)
        
        plt.suptitle('Industry Shareholder Growth Rankings (Last 4 Quarters Average)', 
                    fontsize=14, fontweight='bold', y=0.98)
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_shareholder_rankings.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Chart saved: {output_path}")
        
        plt.show()
    
    def plot_correlation_analysis(self):
        """Plot correlation between shareholder growth and future returns"""
        
        if not hasattr(self, 'industry_summary'):
            print("⚠️ Run analyze_industry_performance() first")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
        
        # Scatter plot: Shareholder growth vs Forward returns
        valid_corr = self.industry_summary[self.industry_summary['correlation'].notna()]
        
        ax1.scatter(valid_corr['pct_shareholders_increasing'], 
                   valid_corr['avg_forward_return'],
                   s=100, alpha=0.6, c=valid_corr['correlation'],
                   cmap='RdYlGn', edgecolors='black', linewidth=0.5)
        
        # Add labels for extreme points
        top_performers = valid_corr.nlargest(3, 'avg_forward_return')
        for _, row in top_performers.iterrows():
            ax1.annotate(row['industry'], 
                        (row['pct_shareholders_increasing'], row['avg_forward_return']),
                        fontsize=8, ha='right')
        
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax1.axvline(x=50, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel('% Stocks with Increasing Shareholders (2Q)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Average 1-Year Forward Return (%)', fontsize=11, fontweight='bold')
        ax1.set_title('Shareholder Growth vs Future Performance', fontsize=12, fontweight='bold', pad=15)
        ax1.grid(True, alpha=0.3)
        
        # Colorbar
        cbar = plt.colorbar(ax1.collections[0], ax=ax1)
        cbar.set_label('Correlation', fontsize=10)
        
        # Bar chart: Correlation by industry (top 15)
        top_corr = valid_corr.nlargest(15, 'correlation')
        colors = ['green' if x > 0 else 'red' for x in top_corr['correlation']]
        
        ax2.barh(range(len(top_corr)), top_corr['correlation'], color=colors, alpha=0.7)
        ax2.set_yticks(range(len(top_corr)))
        ax2.set_yticklabels(top_corr['industry'], fontsize=9)
        ax2.axvline(x=0, color='black', linestyle='-', linewidth=1)
        ax2.set_xlabel('Correlation Coefficient', fontsize=11, fontweight='bold')
        ax2.set_title('Industries with Strongest Correlation\n(Shareholder Growth → Future Returns)', 
                     fontsize=12, fontweight='bold', pad=15)
        ax2.grid(True, alpha=0.3, axis='x')
        ax2.invert_yaxis()
        
        # Add values
        for i, (idx, row) in enumerate(top_corr.iterrows()):
            ax2.text(row['correlation'] + 0.02 if row['correlation'] > 0 else row['correlation'] - 0.02, 
                    i, f"{row['correlation']:.2f}", 
                    va='center', fontsize=8, ha='left' if row['correlation'] > 0 else 'right')
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_path = output_dir / 'industry_correlation_analysis.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Chart saved: {output_path}")
        
        plt.show()
    
    def save_results(self):
        """Save all results to CSV"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        # Save current rankings
        if hasattr(self, 'current_rankings'):
            path1 = output_dir / f'industry_shareholder_rankings_{timestamp}.csv'
            self.current_rankings.to_csv(path1, index=False)
            print(f"✅ Rankings saved: {path1}")
        
        # Save performance analysis
        if hasattr(self, 'industry_summary'):
            path2 = output_dir / f'industry_performance_correlation_{timestamp}.csv'
            self.industry_summary.to_csv(path2, index=False)
            print(f"✅ Correlation analysis saved: {path2}")
        
        # Save quarterly data
        if hasattr(self, 'industry_quarterly'):
            path3 = output_dir / f'industry_quarterly_metrics_{timestamp}.csv'
            self.industry_quarterly.to_csv(path3, index=False)
            print(f"✅ Quarterly metrics saved: {path3}")


def main():
    print("="*80)
    print("INDUSTRY SHAREHOLDER & PERFORMANCE ANALYSIS")
    print("="*80)
    
    analyzer = IndustryShareholderAnalyzer()
    
    # Calculate shareholder changes
    shareholder_data = analyzer.calculate_shareholder_changes()
    
    # Calculate forward returns
    forward_returns = analyzer.calculate_forward_returns(shareholder_data)
    
    if len(forward_returns) > 0:
        # Analyze correlation
        industry_performance, industry_summary = analyzer.analyze_industry_performance()
    
    # Get current rankings
    current_rankings = analyzer.get_current_industry_rankings()
    
    # Print current rankings
    print("\n" + "="*80)
    print("CURRENT INDUSTRY RANKINGS (Last 4 Quarters)")
    print("="*80)
    print("\n🟢 TOP 10 INDUSTRIES - GAINING SHAREHOLDERS:")
    print("-"*80)
    for i, (_, row) in enumerate(current_rankings.head(10).iterrows(), 1):
        print(f"{i:2d}. {row['industry']:40s} | {row['pct_increasing']:5.1f}% | "
              f"Avg Change: {row['avg_pct_change']:+6.1f}% | {int(row['num_stocks'])} stocks")
    
    print("\n🔴 BOTTOM 10 INDUSTRIES - LOSING SHAREHOLDERS:")
    print("-"*80)
    for i, (_, row) in enumerate(current_rankings.tail(10).iterrows(), 1):
        print(f"{i:2d}. {row['industry']:40s} | {row['pct_increasing']:5.1f}% | "
              f"Avg Change: {row['avg_pct_change']:+6.1f}% | {int(row['num_stocks'])} stocks")
    
    # Print correlation analysis
    if hasattr(analyzer, 'industry_summary'):
        print("\n" + "="*80)
        print("PREDICTIVE POWER ANALYSIS")
        print("="*80)
        print("\nIndustries where shareholder growth PREDICTS future returns:")
        print("-"*80)
        
        strong_positive = analyzer.industry_summary[
            analyzer.industry_summary['correlation'] > 0.3
        ].sort_values('correlation', ascending=False)
        
        if len(strong_positive) > 0:
            print("\n✅ Strong Positive Correlation (>0.3):")
            for _, row in strong_positive.iterrows():
                print(f"  {row['industry']:40s} | Correlation: {row['correlation']:+.2f} | "
                      f"Avg Return: {row['avg_forward_return']:+6.1f}%")
        else:
            print("  No industries with strong positive correlation found")
        
        strong_negative = analyzer.industry_summary[
            analyzer.industry_summary['correlation'] < -0.3
        ].sort_values('correlation')
        
        if len(strong_negative) > 0:
            print("\n⚠️ Strong Negative Correlation (<-0.3):")
            for _, row in strong_negative.iterrows():
                print(f"  {row['industry']:40s} | Correlation: {row['correlation']:+.2f} | "
                      f"Avg Return: {row['avg_forward_return']:+6.1f}%")
        else:
            print("  No industries with strong negative correlation found")
    
    # Save results
    analyzer.save_results()
    
    # Plot
    analyzer.plot_top_bottom_industries()
    
    if hasattr(analyzer, 'industry_summary'):
        analyzer.plot_correlation_analysis()
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
