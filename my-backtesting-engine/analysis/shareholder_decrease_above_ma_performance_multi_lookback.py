#!/usr/bin/env python
"""
Shareholder Decrease Performance Analysis - Multiple Lookback Periods

Tests which lookback period gives the best signal:
- 1 Quarter (QoQ)
- 2 Quarters (6 months)
- 4 Quarters (YoY)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class MultiLookbackShareholderAnalyzer:
    """Analyze shareholder changes with multiple lookback periods"""
    
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
        """Load shareholding patterns and price data"""
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date']
        )
        
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"Loaded {len(self.price_df):,} price records")
    
    def _parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings to quarter-end dates"""
        try:
            if '-' in str(quarter_str):
                parts = str(quarter_str).split('-')
                if len(parts) == 2:
                    month_str, year = parts
                    month_map = {
                        'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12,
                        'March': 3, 'June': 6, 'September': 9, 'December': 12
                    }
                    month = month_map.get(month_str, 12)
                    year = int(year)
                    from calendar import monthrange
                    day = monthrange(year, month)[1]
                    return pd.Timestamp(year=year, month=month, day=day)
            return pd.NaT
        except:
            return pd.NaT
    
    def calculate_200day_ma(self):
        """Calculate 200-day moving average"""
        print("\nCalculating 200-day moving averages...")
        
        self.price_df['ma_200'] = self.price_df.groupby('isin')['close'].transform(
            lambda x: x.rolling(window=200, min_periods=200).mean()
        )
        self.price_df['above_ma'] = self.price_df['close'] > self.price_df['ma_200']
        
        print("✅ Calculated 200-day MA")
    
    def calculate_shareholder_changes_multi_lookback(self, lookback_quarters=[1, 2, 4]):
        """
        Calculate shareholder changes for multiple lookback periods
        
        Args:
            lookback_quarters: List of quarters to look back (e.g., [1, 2, 4])
                1 = QoQ (3 months)
                2 = 6 months
                4 = YoY (12 months)
        """
        print(f"\nCalculating shareholder changes for lookback periods: {lookback_quarters} quarters...")
        
        # Parse quarter dates
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        valid_data = self.shareholding_df.dropna(subset=['quarter_date', 'total_shareholders']).copy()
        valid_data = valid_data[valid_data['total_shareholders'] > 0]
        
        # Sort by ISIN and quarter date
        valid_data = valid_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate changes for each lookback period
        for lookback in lookback_quarters:
            col_name = f'prev_{lookback}q_shareholders'
            change_col = f'change_{lookback}q'
            pct_change_col = f'pct_change_{lookback}q'
            trend_col = f'trend_{lookback}q'
            
            # Previous period shareholders
            valid_data[col_name] = valid_data.groupby('isin')['total_shareholders'].shift(lookback)
            
            # Absolute change
            valid_data[change_col] = valid_data['total_shareholders'] - valid_data[col_name]
            
            # Percentage change
            valid_data[pct_change_col] = (valid_data[change_col] / valid_data[col_name]) * 100
            
            # Classify trend
            valid_data[trend_col] = 'Neutral'
            valid_data.loc[valid_data[change_col] > 0, trend_col] = 'Increasing'
            valid_data.loc[valid_data[change_col] < 0, trend_col] = 'Decreasing'
            
            print(f"  ✅ Calculated {lookback}-quarter lookback ({lookback*3} months)")
        
        self.shareholding_with_changes = valid_data
        self.lookback_quarters = lookback_quarters
        
        return valid_data
    
    def calculate_forward_returns(self, holding_periods=[90]):
        """Calculate forward returns for each lookback period"""
        print(f"\nCalculating forward returns for {holding_periods} days...")
        
        results = []
        
        unique_quarters = sorted(self.shareholding_with_changes['quarter_date'].unique())
        # Skip first N quarters based on max lookback
        skip_quarters = max(self.lookback_quarters)
        unique_quarters = unique_quarters[skip_quarters:]
        
        total_quarters = len(unique_quarters)
        print(f"  Analyzing {total_quarters} quarters...")
        
        for i, quarter_date in enumerate(unique_quarters, 1):
            if i % 5 == 0 or i == 1:
                print(f"  Processing quarter {i}/{total_quarters}: {quarter_date.date()}")
            
            quarter_data = self.shareholding_with_changes[
                self.shareholding_with_changes['quarter_date'] == quarter_date
            ].copy()
            
            if len(quarter_data) == 0:
                continue
            
            # Get price data
            quarter_prices = self.price_df[
                (self.price_df['date'] >= quarter_date - pd.Timedelta(days=7)) &
                (self.price_df['date'] <= quarter_date + pd.Timedelta(days=7))
            ].copy()
            
            quarter_prices = quarter_prices.sort_values('date').groupby('isin').last().reset_index()
            
            # Merge
            merged = quarter_data.merge(
                quarter_prices[['isin', 'date', 'close', 'above_ma']],
                on='isin',
                how='inner'
            )
            
            if len(merged) == 0:
                continue
            
            # Calculate returns for each lookback period
            for holding_days in holding_periods:
                for _, row in merged.iterrows():
                    isin = row['isin']
                    entry_date = row['date']
                    entry_price = row['close']
                    above_ma = row['above_ma']
                    
                    # Find exit price
                    exit_date = entry_date + pd.Timedelta(days=holding_days)
                    exit_window = self.price_df[
                        (self.price_df['isin'] == isin) &
                        (self.price_df['date'] >= exit_date - pd.Timedelta(days=5)) &
                        (self.price_df['date'] <= exit_date + pd.Timedelta(days=5))
                    ]
                    
                    if len(exit_window) == 0:
                        continue
                    
                    exit_row = exit_window.iloc[0]
                    exit_price = exit_row['close']
                    actual_exit_date = exit_row['date']
                    
                    # Calculate return
                    returns_pct = ((exit_price - entry_price) / entry_price) * 100
                    
                    # Create result for each lookback period
                    for lookback in self.lookback_quarters:
                        trend_col = f'trend_{lookback}q'
                        pct_change_col = f'pct_change_{lookback}q'
                        prev_col = f'prev_{lookback}q_shareholders'
                        
                        # Only include if we have data for this lookback
                        if pd.notna(row[prev_col]):
                            results.append({
                                'quarter_date': quarter_date,
                                'isin': isin,
                                'company_name': row['company_name'],
                                'entry_date': entry_date,
                                'exit_date': actual_exit_date,
                                'holding_days': holding_days,
                                'lookback_quarters': lookback,
                                'lookback_months': lookback * 3,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'returns_pct': returns_pct,
                                'above_200ma': above_ma,
                                'shareholder_trend': row[trend_col],
                                'shareholder_change_pct': row[pct_change_col]
                            })
        
        results_df = pd.DataFrame(results)
        
        print(f"\n✅ Calculated {len(results_df):,} return observations")
        
        self.returns_df = results_df
        return results_df
    
    def compare_lookback_periods(self):
        """Compare performance across different lookback periods"""
        print("\nComparing lookback periods...")
        
        # Filter for above MA only
        above_ma_df = self.returns_df[self.returns_df['above_200ma'] == True].copy()
        
        # Calculate summary statistics
        summary = above_ma_df.groupby(['lookback_quarters', 'lookback_months', 'shareholder_trend']).agg({
            'returns_pct': ['mean', 'median', 'std', 'count'],
            'isin': 'nunique'
        }).round(2)
        
        summary.columns = ['avg_return', 'median_return', 'std_return', 'num_observations', 'num_stocks']
        summary = summary.reset_index()
        
        # Calculate win rate
        win_rate = above_ma_df.groupby(['lookback_quarters', 'lookback_months', 'shareholder_trend']).apply(
            lambda x: (x['returns_pct'] > 0).sum() / len(x) * 100
        ).reset_index()
        win_rate.columns = ['lookback_quarters', 'lookback_months', 'shareholder_trend', 'win_rate_pct']
        
        summary = summary.merge(win_rate, on=['lookback_quarters', 'lookback_months', 'shareholder_trend'])
        
        # Calculate risk-adjusted return
        summary['risk_adj_return'] = summary['avg_return'] / summary['std_return']
        
        self.lookback_summary = summary
        
        print("\n" + "="*120)
        print("LOOKBACK PERIOD COMPARISON (Above 200-Day MA Only)")
        print("="*120)
        print(summary.to_string(index=False))
        
        return summary
    
    def plot_lookback_comparison(self):
        """Plot comparison of different lookback periods"""
        
        fig, axes = plt.subplots(2, 2, figsize=(18, 12))
        
        # Filter for Decreasing and Increasing only
        decreasing = self.lookback_summary[self.lookback_summary['shareholder_trend'] == 'Decreasing']
        increasing = self.lookback_summary[self.lookback_summary['shareholder_trend'] == 'Increasing']
        
        # Plot 1: Average Returns
        ax1 = axes[0, 0]
        x_pos = np.arange(len(decreasing))
        width = 0.35
        
        bars1 = ax1.bar(x_pos - width/2, decreasing['avg_return'].values,
                       width, label='Decreasing Shareholders', color='#E63946', alpha=0.8)
        bars2 = ax1.bar(x_pos + width/2, increasing['avg_return'].values,
                       width, label='Increasing Shareholders', color='#2A9D8F', alpha=0.8)
        
        ax1.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Average Return (%)', fontsize=11, fontweight='bold')
        ax1.set_title('Average Returns by Lookback Period', fontsize=13, fontweight='bold', pad=15)
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(decreasing['lookback_months'].values)
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom' if height > 0 else 'top',
                        fontsize=9, fontweight='bold')
        
        # Plot 2: Win Rates
        ax2 = axes[0, 1]
        bars1 = ax2.bar(x_pos - width/2, decreasing['win_rate_pct'].values,
                       width, label='Decreasing Shareholders', color='#E63946', alpha=0.8)
        bars2 = ax2.bar(x_pos + width/2, increasing['win_rate_pct'].values,
                       width, label='Increasing Shareholders', color='#2A9D8F', alpha=0.8)
        
        ax2.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Win Rate (%)', fontsize=11, fontweight='bold')
        ax2.set_title('Win Rate by Lookback Period', fontsize=13, fontweight='bold', pad=15)
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(decreasing['lookback_months'].values)
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom',
                        fontsize=9, fontweight='bold')
        
        # Plot 3: Risk-Adjusted Returns
        ax3 = axes[1, 0]
        bars1 = ax3.bar(x_pos - width/2, decreasing['risk_adj_return'].values,
                       width, label='Decreasing Shareholders', color='#E63946', alpha=0.8)
        bars2 = ax3.bar(x_pos + width/2, increasing['risk_adj_return'].values,
                       width, label='Increasing Shareholders', color='#2A9D8F', alpha=0.8)
        
        ax3.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax3.set_ylabel('Risk-Adjusted Return', fontsize=11, fontweight='bold')
        ax3.set_title('Risk-Adjusted Returns by Lookback Period', fontsize=13, fontweight='bold', pad=15)
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(decreasing['lookback_months'].values)
        ax3.legend(fontsize=10)
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 4: Number of Stocks
        ax4 = axes[1, 1]
        bars1 = ax4.bar(x_pos - width/2, decreasing['num_stocks'].values,
                       width, label='Decreasing Shareholders', color='#E63946', alpha=0.8)
        bars2 = ax4.bar(x_pos + width/2, increasing['num_stocks'].values,
                       width, label='Increasing Shareholders', color='#2A9D8F', alpha=0.8)
        
        ax4.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax4.set_ylabel('Number of Stocks', fontsize=11, fontweight='bold')
        ax4.set_title('Sample Size by Lookback Period', fontsize=13, fontweight='bold', pad=15)
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(decreasing['lookback_months'].values)
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3, axis='y')
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}',
                        ha='center', va='bottom',
                        fontsize=9, fontweight='bold')
        
        plt.suptitle('Shareholder Change Lookback Period Comparison (Above 200-Day MA)',
                    fontsize=15, fontweight='bold')
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f'lookback_period_comparison_{timestamp}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Chart saved: {output_path}")
        
        plt.close()
    
    def find_best_lookback(self):
        """Determine which lookback period gives the best signal"""
        print("\n" + "="*120)
        print("BEST LOOKBACK PERIOD ANALYSIS")
        print("="*120)
        
        decreasing = self.lookback_summary[self.lookback_summary['shareholder_trend'] == 'Decreasing']
        increasing = self.lookback_summary[self.lookback_summary['shareholder_trend'] == 'Increasing']
        
        # Rank by different metrics
        best_return_dec = decreasing.loc[decreasing['avg_return'].idxmax()]
        best_winrate_dec = decreasing.loc[decreasing['win_rate_pct'].idxmax()]
        best_risk_adj_dec = decreasing.loc[decreasing['risk_adj_return'].idxmax()]
        
        print(f"\nFor DECREASING Shareholders (Above 200-Day MA):")
        print(f"\nBest Average Return: {best_return_dec['lookback_months']:.0f} months ({best_return_dec['avg_return']:.2f}%)")
        print(f"Best Win Rate: {best_winrate_dec['lookback_months']:.0f} months ({best_winrate_dec['win_rate_pct']:.1f}%)")
        print(f"Best Risk-Adjusted: {best_risk_adj_dec['lookback_months']:.0f} months ({best_risk_adj_dec['risk_adj_return']:.3f})")
        
        best_return_inc = increasing.loc[increasing['avg_return'].idxmax()]
        best_winrate_inc = increasing.loc[increasing['win_rate_pct'].idxmax()]
        best_risk_adj_inc = increasing.loc[increasing['risk_adj_return'].idxmax()]
        
        print(f"\nFor INCREASING Shareholders (Above 200-Day MA):")
        print(f"\nBest Average Return: {best_return_inc['lookback_months']:.0f} months ({best_return_inc['avg_return']:.2f}%)")
        print(f"Best Win Rate: {best_winrate_inc['lookback_months']:.0f} months ({best_winrate_inc['win_rate_pct']:.1f}%)")
        print(f"Best Risk-Adjusted: {best_risk_adj_inc['lookback_months']:.0f} months ({best_risk_adj_inc['risk_adj_return']:.3f})")
        
        # Overall recommendation
        print(f"\n" + "="*120)
        print("RECOMMENDATIONS")
        print("="*120)
        print(f"\n🎯 For DECREASING Shareholders: {best_risk_adj_dec['lookback_months']:.0f} months ({best_risk_adj_dec['lookback_quarters']:.0f} quarters)")
        print(f"   Average Return: {best_risk_adj_dec['avg_return']:.2f}%")
        print(f"   Win Rate: {best_risk_adj_dec['win_rate_pct']:.1f}%")
        print(f"   Risk-Adjusted Return: {best_risk_adj_dec['risk_adj_return']:.3f}")
        print(f"   Sample Size: {best_risk_adj_dec['num_stocks']:.0f} stocks")
        
        print(f"\n🎯 For INCREASING Shareholders: {best_risk_adj_inc['lookback_months']:.0f} months ({best_risk_adj_inc['lookback_quarters']:.0f} quarters)")
        print(f"   Average Return: {best_risk_adj_inc['avg_return']:.2f}%")
        print(f"   Win Rate: {best_risk_adj_inc['win_rate_pct']:.1f}%")
        print(f"   Risk-Adjusted Return: {best_risk_adj_inc['risk_adj_return']:.3f}")
        print(f"   Sample Size: {best_risk_adj_inc['num_stocks']:.0f} stocks")
        
        # Compare decreasing vs increasing at their best lookbacks
        print(f"\n" + "="*120)
        print("DECREASING vs INCREASING COMPARISON")
        print("="*120)
        
        if best_risk_adj_dec['avg_return'] > best_risk_adj_inc['avg_return']:
            diff = best_risk_adj_dec['avg_return'] - best_risk_adj_inc['avg_return']
            print(f"\n✅ DECREASING shareholders outperform by {diff:.2f}% (at {best_risk_adj_dec['lookback_months']:.0f} month lookback)")
        else:
            diff = best_risk_adj_inc['avg_return'] - best_risk_adj_dec['avg_return']
            print(f"\n✅ INCREASING shareholders outperform by {diff:.2f}% (at {best_risk_adj_inc['lookback_months']:.0f} month lookback)")
    
    def save_results(self):
        """Save detailed results to CSV"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        # Save summary
        summary_path = output_dir / f'lookback_comparison_summary_{timestamp}.csv'
        self.lookback_summary.to_csv(summary_path, index=False)
        print(f"\n✅ Summary saved: {summary_path}")
        
        # Save detailed returns
        returns_path = output_dir / f'lookback_comparison_detailed_returns_{timestamp}.csv'
        self.returns_df.to_csv(returns_path, index=False)
        print(f"✅ Detailed returns saved: {returns_path}")


def main():
    print("="*120)
    print("MULTI-LOOKBACK SHAREHOLDER ANALYSIS")
    print("="*120)
    print("\nTesting 3 lookback periods:")
    print("  - 1 Quarter (3 months) - Quick reaction")
    print("  - 2 Quarters (6 months) - Medium-term")
    print("  - 4 Quarters (12 months) - Long-term YoY")
    print("")
    print("Comparing: Decreasing vs Increasing shareholders (above 200-day MA)")
    print("Forward Returns: 90-day holding period")
    print("="*120)
    
    analyzer = MultiLookbackShareholderAnalyzer()
    
    # Calculate 200-day MA
    analyzer.calculate_200day_ma()
    
    # Test multiple lookback periods
    lookback_periods = [1, 2, 4]  # 1Q, 2Q, 4Q (3, 6, 12 months)
    analyzer.calculate_shareholder_changes_multi_lookback(lookback_quarters=lookback_periods)
    
    # Calculate forward returns (90-day holding period)
    analyzer.calculate_forward_returns(holding_periods=[90])
    
    # Compare lookback periods
    analyzer.compare_lookback_periods()
    
    # Plot comparison
    analyzer.plot_lookback_comparison()
    
    # Find best lookback
    analyzer.find_best_lookback()
    
    # Save results
    analyzer.save_results()
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
