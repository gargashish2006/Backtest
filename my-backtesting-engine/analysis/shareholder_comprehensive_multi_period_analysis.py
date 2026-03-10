#!/usr/bin/env python
"""
Comprehensive Shareholder Analysis - Multiple Holding & Lookback Periods

Tests:
- Lookback Periods: 1Q, 2Q, 4Q, 8Q, 12Q (3, 6, 12, 24, 36 months)
- Holding Periods: 90, 180, 365 days
- Compares: Decreasing vs Increasing shareholders (Above 200-Day MA)

Finds optimal combination of lookback and holding periods.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class ComprehensiveShareholderAnalyzer:
    """Comprehensive analysis with multiple periods"""
    
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
        """Load and pre-index data for fast lookups"""
        # Load shareholding
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        
        # Load price data with optimizations
        print("Loading price data (7.1M records)...")
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date'],
            dtype={'isin': 'category', 'close': 'float32', 'volume': 'float32'}
        )
        
        # Sort and create index
        print("Indexing price data for fast lookups...")
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        self.price_df = self.price_df.set_index(['isin', 'date'])
        
        print(f"✅ Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"✅ Loaded and indexed {len(self.price_df):,} price records")
    
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
        
        # Reset index temporarily
        price_df = self.price_df.reset_index()
        
        # Calculate MA
        price_df['ma_200'] = price_df.groupby('isin')['close'].transform(
            lambda x: x.rolling(window=200, min_periods=200).mean()
        )
        price_df['above_ma'] = price_df['close'] > price_df['ma_200']
        
        # Re-index
        self.price_df = price_df.set_index(['isin', 'date'])
        
        print("✅ Calculated 200-day MA")
    
    def calculate_shareholder_changes_multi_lookback(self, lookback_quarters=[1, 2, 4, 8, 12]):
        """
        Calculate shareholder changes for multiple lookback periods
        
        Args:
            lookback_quarters: [1, 2, 4, 8, 12] = [3, 6, 12, 24, 36 months]
        """
        print(f"\nCalculating shareholder changes for lookback periods: {lookback_quarters} quarters...")
        
        # Parse quarter dates
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        valid_data = self.shareholding_df.dropna(subset=['quarter_date', 'total_shareholders']).copy()
        valid_data = valid_data[valid_data['total_shareholders'] > 0]
        
        # Sort
        valid_data = valid_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate changes for each lookback
        for lookback in lookback_quarters:
            col_name = f'prev_{lookback}q_shareholders'
            change_col = f'change_{lookback}q'
            pct_change_col = f'pct_change_{lookback}q'
            trend_col = f'trend_{lookback}q'
            
            valid_data[col_name] = valid_data.groupby('isin')['total_shareholders'].shift(lookback)
            valid_data[change_col] = valid_data['total_shareholders'] - valid_data[col_name]
            valid_data[pct_change_col] = (valid_data[change_col] / valid_data[col_name]) * 100
            
            valid_data[trend_col] = 'Neutral'
            valid_data.loc[valid_data[change_col] > 0, trend_col] = 'Increasing'
            valid_data.loc[valid_data[change_col] < 0, trend_col] = 'Decreasing'
            
            months = lookback * 3
            print(f"  ✅ Calculated {lookback}-quarter lookback ({months} months)")
        
        self.shareholding_with_changes = valid_data
        self.lookback_quarters = lookback_quarters
        
        return valid_data
    
    def calculate_forward_returns_comprehensive(self, holding_periods=[90, 180, 365]):
        """
        Calculate forward returns for multiple holding periods
        
        Args:
            holding_periods: [90, 180, 365] = [3 months, 6 months, 1 year]
        """
        print(f"\nCalculating forward returns for holding periods: {holding_periods} days...")
        
        results = []
        
        # Reset index for easier access
        price_df = self.price_df.reset_index()
        
        # Pre-create date index for fast lookups
        print("Creating date index for fast lookups...")
        date_lookup = {}
        for isin in price_df['isin'].unique():
            stock_dates = price_df[price_df['isin'] == isin][['date', 'close', 'above_ma']].copy()
            stock_dates = stock_dates.sort_values('date')
            date_lookup[isin] = stock_dates
        
        unique_quarters = sorted(self.shareholding_with_changes['quarter_date'].unique())
        skip_quarters = max(self.lookback_quarters)
        unique_quarters = unique_quarters[skip_quarters:]
        
        total_quarters = len(unique_quarters)
        print(f"Processing {total_quarters} quarters for {len(holding_periods)} holding periods...")
        
        for i, quarter_date in enumerate(unique_quarters, 1):
            if i % 5 == 0:
                pct = i/total_quarters*100
                print(f"  Quarter {i}/{total_quarters} ({pct:.1f}%): {quarter_date.date()}")
            
            quarter_data = self.shareholding_with_changes[
                self.shareholding_with_changes['quarter_date'] == quarter_date
            ].copy()
            
            if len(quarter_data) == 0:
                continue
            
            # BATCH PROCESS: Process all stocks for this quarter
            for _, row in quarter_data.iterrows():
                isin = row['isin']
                
                # Skip if no price data
                if isin not in date_lookup:
                    continue
                
                stock_prices = date_lookup[isin]
                
                # Find entry date (closest to quarter date)
                entry_mask = (stock_prices['date'] >= quarter_date - pd.Timedelta(days=7)) & \
                            (stock_prices['date'] <= quarter_date + pd.Timedelta(days=7))
                entry_data = stock_prices[entry_mask]
                
                if len(entry_data) == 0:
                    continue
                
                entry_row = entry_data.iloc[0]
                entry_date = entry_row['date']
                entry_price = entry_row['close']
                above_ma = entry_row['above_ma']
                
                # Calculate returns for ALL holding periods
                for holding_days in holding_periods:
                    exit_date = entry_date + pd.Timedelta(days=holding_days)
                    
                    # Find exit price
                    exit_mask = (stock_prices['date'] >= exit_date - pd.Timedelta(days=5)) & \
                               (stock_prices['date'] <= exit_date + pd.Timedelta(days=5))
                    exit_data = stock_prices[exit_mask]
                    
                    if len(exit_data) == 0:
                        continue
                    
                    exit_row = exit_data.iloc[0]
                    exit_price = exit_row['close']
                    actual_exit_date = exit_row['date']
                    
                    # Calculate return
                    returns_pct = ((exit_price - entry_price) / entry_price) * 100
                    
                    # Annualized return
                    days_held = (actual_exit_date - entry_date).days
                    if days_held > 0:
                        annualized_return = ((1 + returns_pct/100) ** (365/days_held) - 1) * 100
                    else:
                        annualized_return = 0
                    
                    # Store for each lookback period
                    for lookback in self.lookback_quarters:
                        trend_col = f'trend_{lookback}q'
                        pct_change_col = f'pct_change_{lookback}q'
                        prev_col = f'prev_{lookback}q_shareholders'
                        
                        if pd.notna(row[prev_col]):
                            results.append({
                                'quarter_date': quarter_date,
                                'isin': isin,
                                'company_name': row['company_name'],
                                'entry_date': entry_date,
                                'exit_date': actual_exit_date,
                                'holding_days': holding_days,
                                'actual_days_held': days_held,
                                'lookback_quarters': lookback,
                                'lookback_months': lookback * 3,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'returns_pct': returns_pct,
                                'annualized_return_pct': annualized_return,
                                'above_200ma': above_ma,
                                'shareholder_trend': row[trend_col],
                                'shareholder_change_pct': row[pct_change_col]
                            })
            
            # Memory management
            if i % 10 == 0:
                import gc
                gc.collect()
        
        results_df = pd.DataFrame(results)
        
        print(f"\n✅ Calculated {len(results_df):,} return observations")
        print(f"   Combinations: {len(self.lookback_quarters)} lookbacks × {len(holding_periods)} holding periods")
        
        self.returns_df = results_df
        self.holding_periods = holding_periods
        
        return results_df
    
    def analyze_all_combinations(self):
        """Analyze performance across all lookback and holding period combinations"""
        print("\nAnalyzing all combinations...")
        
        # Filter for above MA only
        above_ma_df = self.returns_df[self.returns_df['above_200ma'] == True].copy()
        
        # Calculate summary statistics
        summary = above_ma_df.groupby([
            'lookback_quarters', 'lookback_months', 
            'holding_days', 'shareholder_trend'
        ]).agg({
            'returns_pct': ['mean', 'median', 'std', 'count'],
            'annualized_return_pct': ['mean', 'median'],
            'isin': 'nunique'
        }).round(2)
        
        summary.columns = [
            'avg_return', 'median_return', 'std_return', 'num_observations',
            'avg_annualized', 'median_annualized', 'num_stocks'
        ]
        summary = summary.reset_index()
        
        # Calculate win rate
        win_rate = above_ma_df.groupby([
            'lookback_quarters', 'lookback_months',
            'holding_days', 'shareholder_trend'
        ]).apply(
            lambda x: (x['returns_pct'] > 0).sum() / len(x) * 100, include_groups=False
        ).reset_index()
        win_rate.columns = ['lookback_quarters', 'lookback_months', 'holding_days', 
                           'shareholder_trend', 'win_rate_pct']
        
        summary = summary.merge(win_rate, on=[
            'lookback_quarters', 'lookback_months', 'holding_days', 'shareholder_trend'
        ])
        
        # Calculate risk-adjusted return
        summary['risk_adj_return'] = summary['avg_return'] / summary['std_return']
        
        # Calculate sharpe-like ratio (annualized return / std)
        summary['sharpe_ratio'] = summary['avg_annualized'] / summary['std_return']
        
        self.comprehensive_summary = summary
        
        print("\n" + "="*140)
        print("COMPREHENSIVE ANALYSIS - ALL COMBINATIONS (Above 200-Day MA Only)")
        print("="*140)
        
        # Show summary grouped by holding period
        for holding_days in sorted(summary['holding_days'].unique()):
            print(f"\n📊 HOLDING PERIOD: {holding_days} days ({holding_days/30:.1f} months)")
            print("="*140)
            
            period_data = summary[summary['holding_days'] == holding_days]
            
            # Show decreasing shareholders
            decreasing = period_data[period_data['shareholder_trend'] == 'Decreasing'].sort_values('lookback_months')
            
            if len(decreasing) > 0:
                print("\n🔻 DECREASING Shareholders:")
                print(decreasing[[
                    'lookback_months', 'avg_return', 'avg_annualized', 
                    'win_rate_pct', 'risk_adj_return', 'num_stocks'
                ]].to_string(index=False))
            
            # Show increasing shareholders
            increasing = period_data[period_data['shareholder_trend'] == 'Increasing'].sort_values('lookback_months')
            
            if len(increasing) > 0:
                print("\n🔺 INCREASING Shareholders:")
                print(increasing[[
                    'lookback_months', 'avg_return', 'avg_annualized',
                    'win_rate_pct', 'risk_adj_return', 'num_stocks'
                ]].to_string(index=False))
        
        return summary
    
    def find_optimal_combinations(self):
        """Find the best combinations across all metrics"""
        print("\n" + "="*140)
        print("🎯 OPTIMAL COMBINATIONS ANALYSIS")
        print("="*140)
        
        decreasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Decreasing'
        ].copy()
        
        # Find best for each holding period
        for holding_days in sorted(self.holding_periods):
            print(f"\n{'='*140}")
            print(f"📌 HOLDING PERIOD: {holding_days} days ({holding_days/30:.1f} months, {holding_days/365:.2f} years)")
            print(f"{'='*140}")
            
            period_data = decreasing[decreasing['holding_days'] == holding_days]
            
            if len(period_data) == 0:
                continue
            
            # Best by different metrics
            best_return = period_data.loc[period_data['avg_return'].idxmax()]
            best_annualized = period_data.loc[period_data['avg_annualized'].idxmax()]
            best_winrate = period_data.loc[period_data['win_rate_pct'].idxmax()]
            best_risk_adj = period_data.loc[period_data['risk_adj_return'].idxmax()]
            best_sharpe = period_data.loc[period_data['sharpe_ratio'].idxmax()]
            
            print(f"\n🏆 Best Average Return:")
            print(f"   Lookback: {best_return['lookback_months']:.0f} months | "
                  f"Return: {best_return['avg_return']:.2f}% | "
                  f"Win Rate: {best_return['win_rate_pct']:.1f}% | "
                  f"Stocks: {best_return['num_stocks']:.0f}")
            
            print(f"\n🏆 Best Annualized Return:")
            print(f"   Lookback: {best_annualized['lookback_months']:.0f} months | "
                  f"Annualized: {best_annualized['avg_annualized']:.2f}% | "
                  f"Win Rate: {best_annualized['win_rate_pct']:.1f}% | "
                  f"Stocks: {best_annualized['num_stocks']:.0f}")
            
            print(f"\n🏆 Best Win Rate:")
            print(f"   Lookback: {best_winrate['lookback_months']:.0f} months | "
                  f"Win Rate: {best_winrate['win_rate_pct']:.1f}% | "
                  f"Return: {best_winrate['avg_return']:.2f}% | "
                  f"Stocks: {best_winrate['num_stocks']:.0f}")
            
            print(f"\n🏆 Best Risk-Adjusted Return:")
            print(f"   Lookback: {best_risk_adj['lookback_months']:.0f} months | "
                  f"Risk-Adj: {best_risk_adj['risk_adj_return']:.3f} | "
                  f"Return: {best_risk_adj['avg_return']:.2f}% | "
                  f"Win Rate: {best_risk_adj['win_rate_pct']:.1f}%")
            
            print(f"\n🏆 Best Sharpe Ratio:")
            print(f"   Lookback: {best_sharpe['lookback_months']:.0f} months | "
                  f"Sharpe: {best_sharpe['sharpe_ratio']:.3f} | "
                  f"Annualized: {best_sharpe['avg_annualized']:.2f}% | "
                  f"Win Rate: {best_sharpe['win_rate_pct']:.1f}%")
            
            # Overall recommendation (balanced approach)
            period_data['score'] = (
                period_data['avg_return'].rank(pct=True) * 0.3 +
                period_data['win_rate_pct'].rank(pct=True) * 0.3 +
                period_data['risk_adj_return'].rank(pct=True) * 0.2 +
                period_data['sharpe_ratio'].rank(pct=True) * 0.2
            )
            
            recommended = period_data.loc[period_data['score'].idxmax()]
            
            print(f"\n⭐ RECOMMENDED COMBINATION:")
            print(f"   Lookback: {recommended['lookback_months']:.0f} months ({recommended['lookback_quarters']:.0f} quarters)")
            print(f"   Holding: {holding_days} days ({holding_days/30:.1f} months)")
            print(f"   Expected Return: {recommended['avg_return']:.2f}%")
            print(f"   Annualized Return: {recommended['avg_annualized']:.2f}%")
            print(f"   Win Rate: {recommended['win_rate_pct']:.1f}%")
            print(f"   Risk-Adjusted: {recommended['risk_adj_return']:.3f}")
            print(f"   Sharpe Ratio: {recommended['sharpe_ratio']:.3f}")
            print(f"   Sample Size: {recommended['num_stocks']:.0f} stocks")
    
    def plot_heatmaps(self):
        """Create heatmaps for all metrics"""
        
        decreasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Decreasing'
        ].copy()
        
        increasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Increasing'
        ].copy()
        
        # Create figure with subplots
        fig = plt.figure(figsize=(20, 24))
        
        metrics = [
            ('avg_return', 'Average Return (%)', 'RdYlGn', True),
            ('avg_annualized', 'Annualized Return (%)', 'RdYlGn', True),
            ('win_rate_pct', 'Win Rate (%)', 'YlOrRd', False),
            ('risk_adj_return', 'Risk-Adjusted Return', 'viridis', False),
            ('sharpe_ratio', 'Sharpe Ratio', 'plasma', False),
            ('num_stocks', 'Number of Stocks', 'Blues', False)
        ]
        
        for idx, (metric, title, cmap, center) in enumerate(metrics, 1):
            # Decreasing shareholders
            ax1 = plt.subplot(6, 2, idx*2-1)
            pivot_dec = decreasing.pivot(
                index='lookback_months',
                columns='holding_days',
                values=metric
            )
            
            if center:
                vmin, vmax = pivot_dec.min().min(), pivot_dec.max().max()
                center_val = 0
            else:
                vmin, vmax, center_val = None, None, None
            
            sns.heatmap(pivot_dec, annot=True, fmt='.2f', cmap=cmap,
                       ax=ax1, cbar_kws={'label': metric},
                       vmin=vmin, vmax=vmax, center=center_val)
            
            ax1.set_title(f'DECREASING Shareholders\n{title}', 
                         fontsize=12, fontweight='bold', pad=10)
            ax1.set_xlabel('Holding Period (Days)', fontsize=10, fontweight='bold')
            ax1.set_ylabel('Lookback Period (Months)', fontsize=10, fontweight='bold')
            
            # Increasing shareholders
            ax2 = plt.subplot(6, 2, idx*2)
            pivot_inc = increasing.pivot(
                index='lookback_months',
                columns='holding_days',
                values=metric
            )
            
            sns.heatmap(pivot_inc, annot=True, fmt='.2f', cmap=cmap,
                       ax=ax2, cbar_kws={'label': metric},
                       vmin=vmin, vmax=vmax, center=center_val)
            
            ax2.set_title(f'INCREASING Shareholders\n{title}',
                         fontsize=12, fontweight='bold', pad=10)
            ax2.set_xlabel('Holding Period (Days)', fontsize=10, fontweight='bold')
            ax2.set_ylabel('Lookback Period (Months)', fontsize=10, fontweight='bold')
        
        plt.suptitle('Comprehensive Performance Analysis: All Combinations\n(Above 200-Day MA Only)',
                    fontsize=16, fontweight='bold', y=0.995)
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f'comprehensive_heatmaps_{timestamp}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Heatmaps saved: {output_path}")
        
        plt.close()
    
    def plot_comparison_charts(self):
        """Create comparison charts for key metrics"""
        
        fig, axes = plt.subplots(3, 2, figsize=(18, 16))
        
        decreasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Decreasing'
        ]
        increasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Increasing'
        ]
        
        holding_periods_map = {90: '3M', 180: '6M', 365: '1Y'}
        
        # Plot 1: Average Returns by Lookback (grouped by holding period)
        ax1 = axes[0, 0]
        for holding_days in sorted(self.holding_periods):
            dec_data = decreasing[decreasing['holding_days'] == holding_days]
            ax1.plot(dec_data['lookback_months'], dec_data['avg_return'],
                    marker='o', linewidth=2, markersize=7,
                    label=f'Decreasing - {holding_periods_map[holding_days]}')
        
        ax1.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Average Return (%)', fontsize=11, fontweight='bold')
        ax1.set_title('Average Returns: Decreasing Shareholders', fontsize=13, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 2: Average Returns - Increasing
        ax2 = axes[0, 1]
        for holding_days in sorted(self.holding_periods):
            inc_data = increasing[increasing['holding_days'] == holding_days]
            ax2.plot(inc_data['lookback_months'], inc_data['avg_return'],
                    marker='s', linewidth=2, markersize=7,
                    label=f'Increasing - {holding_periods_map[holding_days]}')
        
        ax2.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Average Return (%)', fontsize=11, fontweight='bold')
        ax2.set_title('Average Returns: Increasing Shareholders', fontsize=13, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 3: Win Rates - Decreasing
        ax3 = axes[1, 0]
        for holding_days in sorted(self.holding_periods):
            dec_data = decreasing[decreasing['holding_days'] == holding_days]
            ax3.plot(dec_data['lookback_months'], dec_data['win_rate_pct'],
                    marker='o', linewidth=2, markersize=7,
                    label=f'Decreasing - {holding_periods_map[holding_days]}')
        
        ax3.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax3.set_ylabel('Win Rate (%)', fontsize=11, fontweight='bold')
        ax3.set_title('Win Rates: Decreasing Shareholders', fontsize=13, fontweight='bold')
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 4: Win Rates - Increasing
        ax4 = axes[1, 1]
        for holding_days in sorted(self.holding_periods):
            inc_data = increasing[increasing['holding_days'] == holding_days]
            ax4.plot(inc_data['lookback_months'], inc_data['win_rate_pct'],
                    marker='s', linewidth=2, markersize=7,
                    label=f'Increasing - {holding_periods_map[holding_days]}')
        
        ax4.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax4.set_ylabel('Win Rate (%)', fontsize=11, fontweight='bold')
        ax4.set_title('Win Rates: Increasing Shareholders', fontsize=13, fontweight='bold')
        ax4.legend(fontsize=9)
        ax4.grid(True, alpha=0.3)
        ax4.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
        
        # Plot 5: Risk-Adjusted Returns - Decreasing
        ax5 = axes[2, 0]
        for holding_days in sorted(self.holding_periods):
            dec_data = decreasing[decreasing['holding_days'] == holding_days]
            ax5.plot(dec_data['lookback_months'], dec_data['risk_adj_return'],
                    marker='o', linewidth=2, markersize=7,
                    label=f'Decreasing - {holding_periods_map[holding_days]}')
        
        ax5.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax5.set_ylabel('Risk-Adjusted Return', fontsize=11, fontweight='bold')
        ax5.set_title('Risk-Adjusted Returns: Decreasing Shareholders', fontsize=13, fontweight='bold')
        ax5.legend(fontsize=9)
        ax5.grid(True, alpha=0.3)
        
        # Plot 6: Risk-Adjusted Returns - Increasing
        ax6 = axes[2, 1]
        for holding_days in sorted(self.holding_periods):
            inc_data = increasing[increasing['holding_days'] == holding_days]
            ax6.plot(inc_data['lookback_months'], inc_data['risk_adj_return'],
                    marker='s', linewidth=2, markersize=7,
                    label=f'Increasing - {holding_periods_map[holding_days]}')
        
        ax6.set_xlabel('Lookback Period (Months)', fontsize=11, fontweight='bold')
        ax6.set_ylabel('Risk-Adjusted Return', fontsize=11, fontweight='bold')
        ax6.set_title('Risk-Adjusted Returns: Increasing Shareholders', fontsize=13, fontweight='bold')
        ax6.legend(fontsize=9)
        ax6.grid(True, alpha=0.3)
        
        plt.suptitle('Comprehensive Performance Comparison (Above 200-Day MA)',
                    fontsize=15, fontweight='bold')
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f'comprehensive_comparison_{timestamp}.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Comparison charts saved: {output_path}")
        
        plt.close()
    
    def save_results(self):
        """Save comprehensive results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        # Save comprehensive summary
        summary_path = output_dir / f'comprehensive_summary_{timestamp}.csv'
        self.comprehensive_summary.to_csv(summary_path, index=False)
        print(f"✅ Comprehensive summary saved: {summary_path}")
        
        # Save detailed returns
        returns_path = output_dir / f'comprehensive_detailed_returns_{timestamp}.csv'
        self.returns_df.to_csv(returns_path, index=False)
        print(f"✅ Detailed returns saved: {returns_path}")
        
        # Create recommendations summary
        recommendations = []
        
        decreasing = self.comprehensive_summary[
            self.comprehensive_summary['shareholder_trend'] == 'Decreasing'
        ].copy()
        
        for holding_days in sorted(self.holding_periods):
            period_data = decreasing[decreasing['holding_days'] == holding_days]
            
            if len(period_data) == 0:
                continue
            
            # Calculate composite score
            period_data['score'] = (
                period_data['avg_return'].rank(pct=True) * 0.3 +
                period_data['win_rate_pct'].rank(pct=True) * 0.3 +
                period_data['risk_adj_return'].rank(pct=True) * 0.2 +
                period_data['sharpe_ratio'].rank(pct=True) * 0.2
            )
            
            recommended = period_data.loc[period_data['score'].idxmax()]
            
            recommendations.append({
                'holding_period_days': holding_days,
                'holding_period_label': f'{holding_days} days ({holding_days/30:.1f} months)',
                'recommended_lookback_months': recommended['lookback_months'],
                'recommended_lookback_quarters': recommended['lookback_quarters'],
                'expected_return_pct': recommended['avg_return'],
                'annualized_return_pct': recommended['avg_annualized'],
                'win_rate_pct': recommended['win_rate_pct'],
                'risk_adjusted_return': recommended['risk_adj_return'],
                'sharpe_ratio': recommended['sharpe_ratio'],
                'sample_size': recommended['num_stocks']
            })
        
        recommendations_df = pd.DataFrame(recommendations)
        rec_path = output_dir / f'recommendations_{timestamp}.csv'
        recommendations_df.to_csv(rec_path, index=False)
        print(f"✅ Recommendations saved: {rec_path}")


def main():
    print("="*140)
    print("COMPREHENSIVE SHAREHOLDER ANALYSIS - MULTIPLE PERIODS")
    print("="*140)
    print("\nTesting:")
    print("  • Lookback Periods: 3, 6, 12, 24, 36 months (1Q, 2Q, 4Q, 8Q, 12Q)")
    print("  • Holding Periods: 90, 180, 365 days (3M, 6M, 1Y)")
    print("  • Total Combinations: 5 lookbacks × 3 holding periods = 15")
    print("\nThis will take approximately 15-20 minutes to complete...")
    
    analyzer = ComprehensiveShareholderAnalyzer()
    
    # Step 1: Calculate 200-day MA
    analyzer.calculate_200day_ma()
    
    # Step 2: Calculate shareholder changes for all lookback periods
    lookback_periods = [1, 2, 4, 8, 12]  # 3, 6, 12, 24, 36 months
    analyzer.calculate_shareholder_changes_multi_lookback(lookback_quarters=lookback_periods)
    
    # Step 3: Calculate forward returns for all holding periods
    holding_periods = [90, 180, 365]  # 3 months, 6 months, 1 year
    analyzer.calculate_forward_returns_comprehensive(holding_periods=holding_periods)
    
    # Step 4: Analyze all combinations
    analyzer.analyze_all_combinations()
    
    # Step 5: Find optimal combinations
    analyzer.find_optimal_combinations()
    
    # Step 6: Create visualizations
    print("\n" + "="*140)
    print("Creating visualizations...")
    analyzer.plot_heatmaps()
    analyzer.plot_comparison_charts()
    
    # Step 7: Save all results
    print("\n" + "="*140)
    print("Saving results...")
    analyzer.save_results()
    
    print("\n" + "="*140)
    print("✅ COMPREHENSIVE ANALYSIS COMPLETE!")
    print("="*140)
    print("\nCheck the outputs folder for:")
    print("  📊 Heatmaps showing all combinations")
    print("  📈 Comparison charts for key metrics")
    print("  📄 Detailed CSV reports")
    print("  🎯 Recommendations for each holding period")
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
