#!/usr/bin/env python
"""
Multi-Lookback Industry Validation - OPTIMIZED VERSION

Compares 2Q, 4Q, and 8Q lookback periods to determine the optimal signal strength
for industry-level momentum strategy.

OPTIMIZATION: Uses pd.merge_asof for O(N log N) performance instead of nested loops.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class IndustryValidatorMultiLookback:
    """Validate industry momentum strategy across multiple lookback periods"""
    
    def __init__(self, base_path=None, min_stocks_per_industry=5):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        self.output_path = base_path / 'analysis' / 'outputs'
        self.min_stocks_per_industry = min_stocks_per_industry
        self.lookback_periods = [2, 4, 8]  # quarters
        
        print("="*80)
        print("INDUSTRY MOMENTUM VALIDATION - MULTI-LOOKBACK COMPARISON (OPTIMIZED)")
        print("="*80)
        print(f"Lookback periods: {self.lookback_periods}")
        print(f"Minimum stocks per industry: {min_stocks_per_industry}")
        print(f"\nLoading data...")
        
        self._load_data()
        self._prepare_data()
    
    def _load_data(self):
        """Load required datasets"""
        print("  Loading shareholding patterns...")
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        
        print("  Loading price data...")
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close']
        )
        
        print("  Loading industry info...")
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'industry']
        )
        
        # Filter valid industries
        self.industry_df = self.industry_df[
            (self.industry_df['industry'].notna()) &
            (self.industry_df['industry'] != 'Not Available')
        ]
        
        print(f"\n  ✅ Loaded:")
        print(f"     - {len(self.shareholding_df):,} shareholding records")
        print(f"     - {len(self.price_df):,} price records")
        print(f"     - {self.industry_df['industry'].nunique():,} unique industries")
    
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
    
    def _prepare_data(self):
        """Prepare industry-level aggregated data for all lookback periods"""
        print("\n  Preparing data...")
        
        # Merge shareholding with industry
        shp_with_industry = self.shareholding_df.merge(
            self.industry_df,
            on='isin',
            how='inner'
        )
        
        print(f"     - Matched {len(shp_with_industry):,} records to industries")
        
        # Parse dates
        print("     - Parsing quarter dates...")
        shp_with_industry['quarter_date'] = shp_with_industry['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        shp_with_industry = shp_with_industry.dropna(
            subset=['quarter_date', 'total_shareholders']
        )
        shp_with_industry = shp_with_industry[
            shp_with_industry['total_shareholders'] > 0
        ]
        
        # Sort
        shp_with_industry = shp_with_industry.sort_values(['isin', 'quarter_date'])
        
        # Calculate stock-level changes for all lookback periods
        for lookback in self.lookback_periods:
            shp_with_industry[f'shareholders_{lookback}q_ago'] = shp_with_industry.groupby('isin')['total_shareholders'].shift(lookback)
            shp_with_industry[f'change_{lookback}q'] = shp_with_industry['total_shareholders'] - shp_with_industry[f'shareholders_{lookback}q_ago']
            shp_with_industry[f'is_increase_{lookback}q'] = shp_with_industry[f'change_{lookback}q'] > 0
        
        # Aggregate to industry level
        print("     - Aggregating to industry level...")
        agg_dict = {'isin': 'count'}
        for lookback in self.lookback_periods:
            agg_dict[f'is_increase_{lookback}q'] = 'sum'
        
        industry_quarterly = shp_with_industry.groupby(['quarter_date', 'industry']).agg(agg_dict).reset_index()
        
        # Rename columns
        new_columns = ['quarter_date', 'industry', 'num_stocks']
        for lookback in self.lookback_periods:
            new_columns.append(f'num_increasing_{lookback}q')
        
        industry_quarterly.columns = new_columns
        
        # Calculate percentages
        for lookback in self.lookback_periods:
            industry_quarterly[f'pct_increasing_{lookback}q'] = (
                industry_quarterly[f'num_increasing_{lookback}q'] / industry_quarterly['num_stocks']
            ) * 100
        
        # Filter industries with minimum stock count
        industry_quarterly = industry_quarterly[
            industry_quarterly['num_stocks'] >= self.min_stocks_per_industry
        ]
        
        # Parse price dates and prepare for merge_asof
        print("     - Preparing price data for optimized lookups...")
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"\n  ✅ Data prepared:")
        print(f"     - Valid industry-quarter records: {len(industry_quarterly):,}")
        print(f"     - Date range: {industry_quarterly['quarter_date'].min().date()} to {industry_quarterly['quarter_date'].max().date()}")
        print(f"     - Unique industries: {industry_quarterly['industry'].nunique():,}")
        print(f"     - Price records: {len(self.price_df):,}")
        
        self.industry_data = industry_quarterly
        self.stock_industry_map = self.industry_df
    
    def calculate_industry_returns_optimized(self):
        """
        Calculate forward returns using dictionary-based optimization.
        
        OPTIMIZATION: Create price lookup dictionaries indexed by (isin, date_bucket)
        to avoid repeatedly filtering 7M price records.
        """
        print("\n  Calculating industry forward returns (OPTIMIZED)...")
        
        forward_horizons = [1, 2, 4, 8]  # quarters
        
        # Step 1: Create price lookup dictionary for faster access
        print("     - Building price lookup index...")
        # Group prices by isin for faster lookup
        price_by_isin = {}
        for isin in self.price_df['isin'].unique():
            isin_prices = self.price_df[self.price_df['isin'] == isin].copy()
            isin_prices = isin_prices.sort_values('date')
            price_by_isin[isin] = isin_prices
        
        print(f"     - Indexed {len(price_by_isin):,} stocks")
        
        # Step 2: Calculate returns for each industry-quarter
        results = []
        total_records = len(self.industry_data)
        processed = 0
        
        for _, row in self.industry_data.iterrows():
            processed += 1
            if processed % 100 == 0:
                print(f"     Processing {processed}/{total_records}...", end='\r')
            
            industry = row['industry']
            quarter_date = row['quarter_date']
            
            # Get all stocks in this industry
            industry_isins = self.stock_industry_map[
                self.stock_industry_map['industry'] == industry
            ]['isin'].tolist()
            
            if len(industry_isins) == 0:
                continue
            
            # Get starting prices using pre-indexed data
            start_prices = {}
            for isin in industry_isins:
                if isin not in price_by_isin:
                    continue
                    
                isin_prices = price_by_isin[isin]
                # Find first price >= quarter_date within 7 days
                mask = (isin_prices['date'] >= quarter_date) & (isin_prices['date'] <= quarter_date + pd.Timedelta(days=7))
                if mask.any():
                    start_prices[isin] = isin_prices[mask].iloc[0]['close']
            
            if len(start_prices) == 0:
                continue
            
            # Calculate forward returns at different horizons
            result = {
                'industry': industry,
                'quarter_date': quarter_date,
                'num_stocks': row['num_stocks']
            }
            
            # Add all lookback signals
            for lookback in self.lookback_periods:
                result[f'pct_increasing_{lookback}q'] = row[f'pct_increasing_{lookback}q']
            
            # Calculate returns for each forward horizon
            for quarters_forward in forward_horizons:
                target_date = quarter_date + pd.DateOffset(months=3*quarters_forward)
                
                returns_list = []
                for isin, start_price in start_prices.items():
                    if isin not in price_by_isin:
                        continue
                    
                    isin_prices = price_by_isin[isin]
                    # Find first price >= target_date within 7 days
                    mask = (isin_prices['date'] >= target_date) & (isin_prices['date'] <= target_date + pd.Timedelta(days=7))
                    if mask.any():
                        end_price = isin_prices[mask].iloc[0]['close']
                        stock_return = ((end_price - start_price) / start_price) * 100
                        # Cap extreme returns
                        stock_return = max(min(stock_return, 10000), -10000)
                        returns_list.append(stock_return)
                
                if len(returns_list) > 0:
                    result[f'return_{quarters_forward}q'] = np.mean(returns_list)
                else:
                    result[f'return_{quarters_forward}q'] = np.nan
            
            results.append(result)
        
        print(f"     ✅ Calculated returns for {len(results):,} industry-quarter observations" + " "*20)
        
        self.returns_df = pd.DataFrame(results)
        return self.returns_df
    
    def analyze_all_lookbacks(self):
        """Run correlation analysis for all lookback periods"""
        print("\n" + "="*80)
        print("CORRELATION ANALYSIS - ALL LOOKBACK PERIODS")
        print("="*80)
        
        results_summary = []
        
        for lookback in self.lookback_periods:
            print(f"\n{'='*80}")
            print(f"LOOKBACK PERIOD: {lookback}Q ({lookback*3} months)")
            print(f"{'='*80}")
            
            signal_col = f'pct_increasing_{lookback}q'
            
            for quarters_forward in [1, 2, 4, 8]:
                return_col = f'return_{quarters_forward}q'
                
                # Get valid data
                df = self.returns_df[[signal_col, return_col]].dropna()
                
                if len(df) < 10:
                    print(f"\n  {lookback}Q → {quarters_forward}Q: Insufficient data")
                    continue
                
                # Remove infinite values
                df = df[np.isfinite(df[signal_col]) & np.isfinite(df[return_col])]
                
                if len(df) < 10:
                    continue
                
                # Calculate correlation
                corr, pval = stats.pearsonr(df[signal_col], df[return_col])
                
                print(f"\n  {lookback}Q → {quarters_forward}Q:")
                print(f"    Correlation: {corr:+.4f}")
                print(f"    P-value: {pval:.4f}")
                print(f"    N: {len(df):,}")
                print(f"    Significant: {'YES ✓' if pval < 0.05 else 'no'}")
                
                results_summary.append({
                    'lookback_q': lookback,
                    'forward_q': quarters_forward,
                    'correlation': corr,
                    'p_value': pval,
                    'n_observations': len(df),
                    'significant': pval < 0.05
                })
        
        self.correlation_summary = pd.DataFrame(results_summary)
        return self.correlation_summary
    
    def analyze_quintile_spreads(self):
        """Analyze quintile spreads for all lookback periods"""
        print("\n" + "="*80)
        print("QUINTILE SPREAD ANALYSIS - ALL LOOKBACK PERIODS")
        print("="*80)
        
        spread_results = []
        
        for lookback in self.lookback_periods:
            print(f"\n{'='*80}")
            print(f"LOOKBACK: {lookback}Q")
            print(f"{'='*80}")
            
            signal_col = f'pct_increasing_{lookback}q'
            
            for quarters_forward in [1, 2, 4, 8]:
                return_col = f'return_{quarters_forward}q'
                
                df = self.returns_df[[signal_col, return_col]].dropna()
                df = df[np.isfinite(df[signal_col]) & np.isfinite(df[return_col])]
                
                if len(df) < 25:  # Need at least 5 per quintile
                    continue
                
                # Create quintiles - handle case where duplicates reduce bin count
                try:
                    df['quintile'] = pd.qcut(df[signal_col], q=5, labels=False, duplicates='drop')
                    # Map to Q1-Q5 based on actual number of bins created
                    n_bins = df['quintile'].nunique()
                    if n_bins < 3:  # Need at least 3 bins for meaningful analysis
                        continue
                    df['quintile'] = df['quintile'].apply(lambda x: f'Q{int(x)+1}')
                except ValueError:
                    continue
                
                # Calculate mean returns by quintile
                quintile_returns = df.groupby('quintile')[return_col].mean()
                
                print(f"\n  {lookback}Q → {quarters_forward}Q:")
                quintile_labels = sorted(quintile_returns.index, key=lambda x: int(x[1]))  # Sort Q1, Q2, etc.
                for q in quintile_labels:
                    print(f"    {q}: {quintile_returns[q]:+.2f}%")
                
                # Calculate spread between highest and lowest quintile
                if len(quintile_labels) >= 2:
                    q_low = quintile_labels[0]
                    q_high = quintile_labels[-1]
                    spread = quintile_returns[q_high] - quintile_returns[q_low]
                    print(f"    Spread ({q_high}-{q_low}): {spread:+.2f}%")
                    
                    spread_results.append({
                        'lookback_q': lookback,
                        'forward_q': quarters_forward,
                        'q1_return': quintile_returns[q_low],
                        'q5_return': quintile_returns[q_high],
                        'spread': spread
                    })
        
        self.spread_summary = pd.DataFrame(spread_results)
        return self.spread_summary
    
    def create_comparison_charts(self):
        """Create comprehensive comparison charts across all lookback periods"""
        print("\n  Creating comparison charts...")
        
        # Create figure with 3x3 grid
        fig = plt.figure(figsize=(20, 16))
        
        # Chart 1: Correlation Heatmap
        ax1 = plt.subplot(3, 3, 1)
        corr_pivot = self.correlation_summary.pivot(
            index='lookback_q',
            columns='forward_q',
            values='correlation'
        )
        sns.heatmap(corr_pivot, annot=True, fmt='.4f', cmap='RdYlGn', center=0,
                    ax=ax1, cbar_kws={'label': 'Correlation'})
        ax1.set_title('Correlation Heatmap\n(Lookback vs Forward Period)', fontweight='bold')
        ax1.set_xlabel('Forward Period (Quarters)')
        ax1.set_ylabel('Lookback Period (Quarters)')
        
        # Chart 2: Correlation Strength by Lookback
        ax2 = plt.subplot(3, 3, 2)
        for lookback in self.lookback_periods:
            data = self.correlation_summary[self.correlation_summary['lookback_q'] == lookback]
            ax2.plot(data['forward_q'], data['correlation'], marker='o', label=f'{lookback}Q lookback', linewidth=2)
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax2.set_xlabel('Forward Period (Quarters)')
        ax2.set_ylabel('Correlation')
        ax2.set_title('Correlation by Forward Period', fontweight='bold')
        ax2.legend()
        ax2.grid(alpha=0.3)
        
        # Chart 3: Statistical Significance
        ax3 = plt.subplot(3, 3, 3)
        sig_pivot = self.correlation_summary.pivot(
            index='lookback_q',
            columns='forward_q',
            values='significant'
        )
        sns.heatmap(sig_pivot.astype(float), annot=True, fmt='.0f', cmap='Greens',
                    ax=ax3, cbar=False, vmin=0, vmax=1)
        ax3.set_title('Statistical Significance\n(1 = p < 0.05)', fontweight='bold')
        ax3.set_xlabel('Forward Period (Quarters)')
        ax3.set_ylabel('Lookback Period (Quarters)')
        
        # Chart 4: Spread Heatmap
        ax4 = plt.subplot(3, 3, 4)
        spread_pivot = self.spread_summary.pivot(
            index='lookback_q',
            columns='forward_q',
            values='spread'
        )
        sns.heatmap(spread_pivot, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
                    ax=ax4, cbar_kws={'label': 'Spread %'})
        ax4.set_title('Quintile Spread (Q5-Q1)\n% Returns', fontweight='bold')
        ax4.set_xlabel('Forward Period (Quarters)')
        ax4.set_ylabel('Lookback Period (Quarters)')
        
        # Chart 5: Spread by Forward Period
        ax5 = plt.subplot(3, 3, 5)
        for lookback in self.lookback_periods:
            data = self.spread_summary[self.spread_summary['lookback_q'] == lookback]
            ax5.plot(data['forward_q'], data['spread'], marker='o', label=f'{lookback}Q lookback', linewidth=2)
        ax5.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        ax5.set_xlabel('Forward Period (Quarters)')
        ax5.set_ylabel('Spread (Q5-Q1) %')
        ax5.set_title('Top-Bottom Quintile Spread', fontweight='bold')
        ax5.legend()
        ax5.grid(alpha=0.3)
        
        # Chart 6: Absolute Correlation Strength
        ax6 = plt.subplot(3, 3, 6)
        for lookback in self.lookback_periods:
            data = self.correlation_summary[self.correlation_summary['lookback_q'] == lookback]
            ax6.plot(data['forward_q'], data['correlation'].abs(), marker='o', label=f'{lookback}Q lookback', linewidth=2)
        ax6.set_xlabel('Forward Period (Quarters)')
        ax6.set_ylabel('|Correlation|')
        ax6.set_title('Absolute Correlation Strength', fontweight='bold')
        ax6.legend()
        ax6.grid(alpha=0.3)
        
        # Chart 7-9: Quintile Returns by Lookback Period
        for i, lookback in enumerate(self.lookback_periods, start=7):
            ax = plt.subplot(3, 3, i)
            
            data_lookback = self.spread_summary[self.spread_summary['lookback_q'] == lookback]
            
            x = np.arange(len(data_lookback))
            width = 0.35
            
            ax.bar(x - width/2, data_lookback['q1_return'], width, label='Q1 (Low Participation)', color='#ff6b6b')
            ax.bar(x + width/2, data_lookback['q5_return'], width, label='Q5 (High Participation)', color='#51cf66')
            
            ax.set_xlabel('Forward Period (Quarters)')
            ax.set_ylabel('Return %')
            ax.set_title(f'{lookback}Q Lookback: Quintile Returns', fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(data_lookback['forward_q'])
            ax.legend()
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.3)
            ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = self.output_path / 'charts' / 'validation'
        chart_path.mkdir(parents=True, exist_ok=True)
        output_file = chart_path / 'industry_multi_lookback_comparison.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"     ✅ Saved: {output_file}")
        
        plt.close()
    
    def save_results(self):
        """Save all results to CSV files"""
        print("\n  Saving results...")
        
        report_path = self.output_path / 'reports' / 'validation'
        report_path.mkdir(parents=True, exist_ok=True)
        
        # Save correlation summary
        corr_file = report_path / 'industry_multi_lookback_correlations.csv'
        self.correlation_summary.to_csv(corr_file, index=False)
        print(f"     ✅ Saved: {corr_file}")
        
        # Save spread summary
        spread_file = report_path / 'industry_multi_lookback_spreads.csv'
        self.spread_summary.to_csv(spread_file, index=False)
        print(f"     ✅ Saved: {spread_file}")
        
        # Save full returns data
        returns_file = report_path / 'industry_multi_lookback_returns.csv'
        self.returns_df.to_csv(returns_file, index=False)
        print(f"     ✅ Saved: {returns_file}")
    
    def run_full_analysis(self):
        """Run complete multi-lookback validation"""
        print("\n" + "="*80)
        print("STARTING MULTI-LOOKBACK VALIDATION")
        print("="*80)
        
        # Calculate returns
        self.calculate_industry_returns_optimized()
        
        # Run all analyses
        self.analyze_all_lookbacks()
        self.analyze_quintile_spreads()
        
        # Create visualizations
        self.create_comparison_charts()
        
        # Save results
        self.save_results()
        
        # Print summary
        print("\n" + "="*80)
        print("SUMMARY - OPTIMAL LOOKBACK PERIOD")
        print("="*80)
        
        # Find strongest signals
        best_corr = self.correlation_summary.loc[self.correlation_summary['correlation'].abs().idxmax()]
        best_spread = self.spread_summary.loc[self.spread_summary['spread'].abs().idxmax()]
        
        print(f"\nStrongest Correlation:")
        print(f"  {best_corr['lookback_q']}Q lookback → {best_corr['forward_q']}Q forward")
        print(f"  Correlation: {best_corr['correlation']:+.4f}")
        print(f"  P-value: {best_corr['p_value']:.4f}")
        
        print(f"\nLargest Quintile Spread:")
        print(f"  {best_spread['lookback_q']}Q lookback → {best_spread['forward_q']}Q forward")
        print(f"  Spread: {best_spread['spread']:+.2f}%")
        print(f"  Q1: {best_spread['q1_return']:+.2f}% | Q5: {best_spread['q5_return']:+.2f}%")
        
        # Recommendation
        print(f"\n" + "="*80)
        print("RECOMMENDATION")
        print("="*80)
        
        # Average absolute correlation by lookback
        avg_corr_by_lookback = self.correlation_summary.groupby('lookback_q')['correlation'].apply(lambda x: x.abs().mean())
        best_lookback = avg_corr_by_lookback.idxmax()
        
        print(f"\nOptimal Lookback Period: {best_lookback}Q ({best_lookback*3} months)")
        print(f"Average |Correlation|: {avg_corr_by_lookback[best_lookback]:.4f}")
        
        print("\nAverage Absolute Correlations by Lookback:")
        for lb in self.lookback_periods:
            print(f"  {lb}Q: {avg_corr_by_lookback[lb]:.4f}")
        
        print("\n" + "="*80)
        print("VALIDATION COMPLETE")
        print("="*80)


def main():
    """Main execution function"""
    validator = IndustryValidatorMultiLookback(min_stocks_per_industry=5)
    validator.run_full_analysis()


if __name__ == '__main__':
    main()
