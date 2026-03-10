#!/usr/bin/env python
"""
ULTRA-FAST VERSION - Shareholder Lookback Analysis
Minimal memory footprint, dictionary-based lookups, no indexing overhead
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class FastShareholderAnalyzer:
    """Ultra-fast version with minimal data loading and dict lookups"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading data (optimized)...")
        self._load_data_fast()
    
    def _load_data_fast(self):
        """Load data with minimal memory - only what we need"""
        # Load shareholding
        print("  Loading shareholding data...")
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        print(f"  ✅ {len(self.shareholding_df):,} shareholding records")
        
        # Load price data - optimized with chunking
        print("  Loading price data in chunks...")
        chunks = []
        chunk_size = 500000
        
        for i, chunk in enumerate(pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close'],
            parse_dates=['date'],
            dtype={'isin': 'str', 'close': 'float32'},
            chunksize=chunk_size
        ), 1):
            chunks.append(chunk)
            if i % 10 == 0:
                print(f"    Loaded {i * chunk_size:,} records...")
        
        self.price_df = pd.concat(chunks, ignore_index=True)
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"  ✅ {len(self.price_df):,} price records loaded")
        
        # Create fast lookup dictionary
        print("  Creating fast lookup structure...")
        self.price_lookup = {}
        for isin, group in self.price_df.groupby('isin'):
            self.price_lookup[isin] = group[['date', 'close']].values
        
        print(f"  ✅ Created lookup for {len(self.price_lookup):,} stocks")
        
        # Clear memory
        del self.price_df
        import gc
        gc.collect()
    
    def _parse_quarter(self, quarter_str):
        """Parse quarter string to date"""
        try:
            if '-' in str(quarter_str):
                parts = str(quarter_str).split('-')
                if len(parts) == 2:
                    month_map = {'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12,
                                'March': 3, 'June': 6, 'September': 9, 'December': 12}
                    month = month_map.get(parts[0], 12)
                    year = int(parts[1])
                    from calendar import monthrange
                    day = monthrange(year, month)[1]
                    return pd.Timestamp(year=year, month=month, day=day)
        except:
            pass
        return pd.NaT
    
    def calculate_ma_and_trends(self):
        """Calculate MA and shareholder trends"""
        print("\nCalculating 200-day MA...")
        
        # Calculate MA for each stock
        ma_data = {}
        for isin, prices in self.price_lookup.items():
            dates = prices[:, 0]
            closes = prices[:, 1]
            
            # Calculate 200-day MA
            ma_200 = pd.Series(closes).rolling(window=200, min_periods=200).mean().values
            above_ma = closes > ma_200
            
            # Store as dict: date -> (close, above_ma)
            ma_data[isin] = {dates[i]: (closes[i], above_ma[i]) for i in range(len(dates))}
        
        self.ma_data = ma_data
        print("  ✅ Calculated MA for all stocks")
        
        # Calculate shareholder changes
        print("\nCalculating shareholder changes...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(self._parse_quarter)
        
        valid_data = self.shareholding_df.dropna(subset=['quarter_date', 'total_shareholders']).copy()
        valid_data = valid_data[valid_data['total_shareholders'] > 0]
        valid_data = valid_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate for all lookback periods
        for lookback in [1, 2, 4]:
            prev_col = f'prev_{lookback}q'
            change_col = f'change_{lookback}q'
            trend_col = f'trend_{lookback}q'
            
            valid_data[prev_col] = valid_data.groupby('isin')['total_shareholders'].shift(lookback)
            valid_data[change_col] = valid_data['total_shareholders'] - valid_data[prev_col]
            
            valid_data[trend_col] = 'Neutral'
            valid_data.loc[valid_data[change_col] > 0, trend_col] = 'Increasing'
            valid_data.loc[valid_data[change_col] < 0, trend_col] = 'Decreasing'
            
            print(f"  ✅ {lookback}-quarter lookback")
        
        self.shareholding_data = valid_data
    
    def find_nearest_price(self, isin, target_date, window_days=7):
        """Find nearest price within window"""
        if isin not in self.ma_data:
            return None, None, None
        
        stock_data = self.ma_data[isin]
        dates = list(stock_data.keys())
        
        # Find closest date within window
        target_ts = pd.Timestamp(target_date)
        min_diff = pd.Timedelta(days=window_days+ 1)
        closest_date = None
        
        for date in dates:
            diff = abs(date - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest_date = date
        
        if closest_date is None:
            return None, None, None
        
        close_price, above_ma = stock_data[closest_date]
        return closest_date, close_price, above_ma
    
    def calculate_returns(self):
        """Calculate forward returns - fast version"""
        print("\nCalculating forward returns...")
        
        results = []
        quarters = sorted(self.shareholding_data['quarter_date'].unique())[4:]  # Skip first 4
        
        total = len(quarters)
        for i, quarter_date in enumerate(quarters, 1):
            if i % 5 == 0:
                print(f"  Quarter {i}/{total} ({i/total*100:.0f}%): {quarter_date.date()}")
            
            quarter_stocks = self.shareholding_data[
                self.shareholding_data['quarter_date'] == quarter_date
            ]
            
            for _, row in quarter_stocks.iterrows():
                isin = row['isin']
                
                # Find entry price
                entry_date, entry_price, above_ma = self.find_nearest_price(isin, quarter_date)
                
                if entry_date is None or pd.isna(above_ma):
                    continue
                
                # Find exit price (90 days later)
                exit_target = entry_date + pd.Timedelta(days=90)
                exit_date, exit_price, _ = self.find_nearest_price(isin, exit_target, window_days=5)
                
                if exit_date is None:
                    continue
                
                # Calculate return
                returns_pct = ((exit_price - entry_price) / entry_price) * 100
                
                # Add for each lookback
                for lookback in [1, 2, 4]:
                    trend_col = f'trend_{lookback}q'
                    prev_col = f'prev_{lookback}q'
                    
                    if pd.notna(row[prev_col]):
                        results.append({
                            'quarter_date': quarter_date,
                            'isin': isin,
                            'company_name': row['company_name'],
                            'lookback_quarters': lookback,
                            'lookback_months': lookback * 3,
                            'returns_pct': returns_pct,
                            'above_200ma': above_ma,
                            'shareholder_trend': row[trend_col]
                        })
        
        self.returns_df = pd.DataFrame(results)
        print(f"\n✅ Calculated {len(self.returns_df):,} return observations")
    
    def analyze_results(self):
        """Analyze and compare results"""
        print("\nAnalyzing results...")
        
        # Filter for above MA
        above_ma = self.returns_df[self.returns_df['above_200ma'] == True]
        
        # Group by lookback and trend
        summary = above_ma.groupby(['lookback_months', 'shareholder_trend']).agg({
            'returns_pct': ['mean', 'median', 'std', 'count'],
            'isin': 'nunique'
        }).round(2)
        
        summary.columns = ['avg_return', 'median_return', 'std_return', 'num_obs', 'num_stocks']
        summary = summary.reset_index()
        
        # Win rate
        win_rate = above_ma.groupby(['lookback_months', 'shareholder_trend']).apply(
            lambda x: (x['returns_pct'] > 0).mean() * 100
        ).reset_index(name='win_rate_pct')
        
        summary = summary.merge(win_rate, on=['lookback_months', 'shareholder_trend'])
        summary['risk_adj'] = summary['avg_return'] / summary['std_return']
        
        self.summary = summary
        
        print("\n" + "="*100)
        print("RESULTS: Above 200-Day MA Only")
        print("="*100)
        print(summary.to_string(index=False))
        
        return summary
    
    def plot_results(self):
        """Plot comparison"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        
        decreasing = self.summary[self.summary['shareholder_trend'] == 'Decreasing']
        increasing = self.summary[self.summary['shareholder_trend'] == 'Increasing']
        
        # Plot 1: Returns
        ax1 = axes[0, 0]
        x = np.arange(len(decreasing))
        width = 0.35
        
        ax1.bar(x - width/2, decreasing['avg_return'].values, width,
                label='Decreasing', color='#E63946', alpha=0.8)
        ax1.bar(x + width/2, increasing['avg_return'].values, width,
                label='Increasing', color='#2A9D8F', alpha=0.8)
        ax1.set_xticks(x)
        ax1.set_xticklabels(decreasing['lookback_months'].values)
        ax1.set_xlabel('Lookback (Months)', fontweight='bold')
        ax1.set_ylabel('Avg Return (%)', fontweight='bold')
        ax1.set_title('Average Returns', fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 2: Win Rate
        ax2 = axes[0, 1]
        ax2.bar(x - width/2, decreasing['win_rate_pct'].values, width,
                label='Decreasing', color='#E63946', alpha=0.8)
        ax2.bar(x + width/2, increasing['win_rate_pct'].values, width,
                label='Increasing', color='#2A9D8F', alpha=0.8)
        ax2.set_xticks(x)
        ax2.set_xticklabels(decreasing['lookback_months'].values)
        ax2.set_xlabel('Lookback (Months)', fontweight='bold')
        ax2.set_ylabel('Win Rate (%)', fontweight='bold')
        ax2.set_title('Win Rates', fontweight='bold')
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 3: Risk-Adjusted
        ax3 = axes[1, 0]
        ax3.bar(x - width/2, decreasing['risk_adj'].values, width,
                label='Decreasing', color='#E63946', alpha=0.8)
        ax3.bar(x + width/2, increasing['risk_adj'].values, width,
                label='Increasing', color='#2A9D8F', alpha=0.8)
        ax3.set_xticks(x)
        ax3.set_xticklabels(decreasing['lookback_months'].values)
        ax3.set_xlabel('Lookback (Months)', fontweight='bold')
        ax3.set_ylabel('Risk-Adjusted Return', fontweight='bold')
        ax3.set_title('Risk-Adjusted Returns', fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Plot 4: Sample Size
        ax4 = axes[1, 1]
        ax4.bar(x - width/2, decreasing['num_stocks'].values, width,
                label='Decreasing', color='#E63946', alpha=0.8)
        ax4.bar(x + width/2, increasing['num_stocks'].values, width,
                label='Increasing', color='#2A9D8F', alpha=0.8)
        ax4.set_xticks(x)
        ax4.set_xticklabels(decreasing['lookback_months'].values)
        ax4.set_xlabel('Lookback (Months)', fontweight='bold')
        ax4.set_ylabel('Number of Stocks', fontweight='bold')
        ax4.set_title('Sample Size', fontweight='bold')
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')
        
        plt.suptitle('Shareholder Lookback Analysis (Above 200-Day MA)', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f'lookback_analysis_{timestamp}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Chart saved: {output_path}")
        
        plt.close()
    
    def print_recommendations(self):
        """Print best lookback recommendations"""
        print("\n" + "="*100)
        print("RECOMMENDATIONS")
        print("="*100)
        
        for trend in ['Decreasing', 'Increasing']:
            data = self.summary[self.summary['shareholder_trend'] == trend]
            if len(data) > 0:
                best = data.loc[data['risk_adj'].idxmax()]
                print(f"\n{trend} Shareholders (Above 200-Day MA):")
                print(f"  Best Lookback: {best['lookback_months']:.0f} months")
                print(f"  Avg Return: {best['avg_return']:.2f}%")
                print(f"  Win Rate: {best['win_rate_pct']:.1f}%")
                print(f"  Risk-Adjusted: {best['risk_adj']:.3f}")
                print(f"  Sample: {best['num_stocks']:.0f} stocks")


def main():
    print("="*100)
    print("ULTRA-FAST SHAREHOLDER LOOKBACK ANALYSIS")
    print("="*100)
    print("Testing: 3, 6, 12 month lookbacks | 90-day forward returns")
    print("="*100)
    
    analyzer = FastShareholderAnalyzer()
    analyzer.calculate_ma_and_trends()
    analyzer.calculate_returns()
    analyzer.analyze_results()
    analyzer.plot_results()
    analyzer.print_recommendations()
    
    # Save results
    output_dir = analyzer.base_path / 'analysis' / 'outputs' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d')
    
    summary_path = output_dir / f'lookback_summary_{timestamp}.csv'
    analyzer.summary.to_csv(summary_path, index=False)
    print(f"\n✅ Summary saved: {summary_path}")
    
    returns_path = output_dir / f'lookback_returns_{timestamp}.csv'
    analyzer.returns_df.to_csv(returns_path, index=False)
    print(f"✅ Returns saved: {returns_path}")
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
