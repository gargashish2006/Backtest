#!/usr/bin/env python
"""
Validation Studies for Industry-Level Contrarian Strategy

Tests whether industries with declining retail participation (lower % of stocks 
with increasing shareholders) outperform industries with high retail participation.

Compares to stock-level validation to determine optimal granularity.

Three core studies:
1. Lead-Lag Correlation Analysis (industry level)
2. Persistence (Duration) Analysis
3. Magnitude (Size Effect) Analysis
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class IndustryContrarianValidator:
    """Validate contrarian strategy at INDUSTRY level"""
    
    def __init__(self, base_path=None, min_stocks_per_industry=5):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        self.min_stocks_per_industry = min_stocks_per_industry
        
        print("="*80)
        print("INDUSTRY-LEVEL CONTRARIAN STRATEGY VALIDATION")
        print("="*80)
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
        """Prepare industry-level aggregated data"""
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
        
        # Calculate stock-level changes (1Q lookback)
        shp_with_industry['shareholders_1q_ago'] = shp_with_industry.groupby('isin')['total_shareholders'].shift(1)
        shp_with_industry['change_1q'] = shp_with_industry['total_shareholders'] - shp_with_industry['shareholders_1q_ago']
        shp_with_industry['is_increase_1q'] = shp_with_industry['change_1q'] > 0
        
        # Calculate 2Q changes
        shp_with_industry['shareholders_2q_ago'] = shp_with_industry.groupby('isin')['total_shareholders'].shift(2)
        shp_with_industry['change_2q'] = shp_with_industry['total_shareholders'] - shp_with_industry['shareholders_2q_ago']
        shp_with_industry['is_increase_2q'] = shp_with_industry['change_2q'] > 0
        
        # Calculate 4Q changes
        shp_with_industry['shareholders_4q_ago'] = shp_with_industry.groupby('isin')['total_shareholders'].shift(4)
        shp_with_industry['change_4q'] = shp_with_industry['total_shareholders'] - shp_with_industry['shareholders_4q_ago']
        shp_with_industry['is_increase_4q'] = shp_with_industry['change_4q'] > 0
        
        # Aggregate to industry level
        print("     - Aggregating to industry level...")
        industry_quarterly = shp_with_industry.groupby(['quarter_date', 'industry']).agg({
            'isin': 'count',
            'is_increase_1q': 'sum',
            'is_increase_2q': 'sum',
            'is_increase_4q': 'sum',
            'total_shareholders': 'sum'
        }).reset_index()
        
        industry_quarterly.columns = [
            'quarter_date', 'industry', 'num_stocks',
            'num_increasing_1q', 'num_increasing_2q', 'num_increasing_4q',
            'total_shareholders'
        ]
        
        # Calculate percentages
        industry_quarterly['pct_increasing_1q'] = (
            industry_quarterly['num_increasing_1q'] / industry_quarterly['num_stocks']
        ) * 100
        
        industry_quarterly['pct_increasing_2q'] = (
            industry_quarterly['num_increasing_2q'] / industry_quarterly['num_stocks']
        ) * 100
        
        industry_quarterly['pct_increasing_4q'] = (
            industry_quarterly['num_increasing_4q'] / industry_quarterly['num_stocks']
        ) * 100
        
        # Filter industries with minimum stock count
        industry_quarterly = industry_quarterly[
            industry_quarterly['num_stocks'] >= self.min_stocks_per_industry
        ]
        
        # Parse price dates
        print("     - Parsing price dates...")
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"\n  ✅ Data prepared:")
        print(f"     - Valid industry-quarter records: {len(industry_quarterly):,}")
        print(f"     - Date range: {industry_quarterly['quarter_date'].min().date()} to {industry_quarterly['quarter_date'].max().date()}")
        print(f"     - Unique industries: {industry_quarterly['industry'].nunique():,}")
        print(f"     - Price records: {len(self.price_df):,}")
        
        self.industry_data = industry_quarterly
        self.stock_industry_map = self.industry_df
    
    def calculate_industry_returns(self):
        """Calculate forward returns for each industry at each quarter"""
        print("\n  Calculating industry forward returns...")
        
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
            
            # Get prices at quarter date
            prices_at_quarter = self.price_df[
                (self.price_df['isin'].isin(industry_isins)) &
                (self.price_df['date'] >= quarter_date) &
                (self.price_df['date'] <= quarter_date + pd.Timedelta(days=7))
            ].sort_values('date').groupby('isin').first().reset_index()
            
            if len(prices_at_quarter) == 0:
                continue
            
            # Calculate forward returns at different horizons
            result = {
                'industry': industry,
                'quarter_date': quarter_date,
                'num_stocks': row['num_stocks'],
                'pct_increasing_1q': row['pct_increasing_1q'],
                'pct_increasing_2q': row['pct_increasing_2q'],
                'pct_increasing_4q': row['pct_increasing_4q']
            }
            
            for quarters_forward in [1, 2, 4, 8]:
                target_date = quarter_date + pd.DateOffset(months=3*quarters_forward)
                
                prices_forward = self.price_df[
                    (self.price_df['isin'].isin(industry_isins)) &
                    (self.price_df['date'] >= target_date) &
                    (self.price_df['date'] <= target_date + pd.Timedelta(days=7))
                ].sort_values('date').groupby('isin').first().reset_index()
                
                # Calculate returns for stocks with both prices
                merged = prices_at_quarter[['isin', 'close']].merge(
                    prices_forward[['isin', 'close']],
                    on='isin',
                    suffixes=('_start', '_end')
                )
                
                if len(merged) > 0:
                    merged['return'] = ((merged['close_end'] - merged['close_start']) / merged['close_start']) * 100
                    
                    # Cap extreme returns
                    merged['return'] = merged['return'].clip(-10000, 10000)
                    
                    # Equal-weighted industry return
                    industry_return = merged['return'].mean()
                    result[f'return_{quarters_forward}q'] = industry_return
                else:
                    result[f'return_{quarters_forward}q'] = np.nan
            
            results.append(result)
        
        print(f"     ✅ Calculated returns for {len(results):,} industry-quarter observations" + " "*20)
        
        self.returns_df = pd.DataFrame(results)
        return self.returns_df
    
    def calculate_industry_changes(self):
        """Calculate quarter-over-quarter changes in industry shareholder participation"""
        print("\n  Calculating industry-level shareholder changes...")
        
        df = self.returns_df.copy()
        df = df.sort_values(['industry', 'quarter_date'])
        
        # Calculate changes in % increasing (different lookbacks)
        for lag in [1, 2, 4]:
            df[f'pct_increasing_{lag}q_ago'] = df.groupby('industry')[f'pct_increasing_{lag}q'].shift(1)
            df[f'change_pct_{lag}q'] = df[f'pct_increasing_{lag}q'] - df[f'pct_increasing_{lag}q_ago']
        
        # Remove first observations
        df = df.dropna(subset=['pct_increasing_1q_ago'])
        
        print(f"     ✅ Calculated changes for {len(df):,} observations")
        
        self.analysis_df = df
        return df
    
    #########################################################################
    # STUDY 1: LEAD-LAG CORRELATION ANALYSIS
    #########################################################################
    
    def study_1_lead_lag_correlation(self):
        """Study 1: Industry-level lead-lag correlation"""
        print("\n" + "="*80)
        print("STUDY 1: LEAD-LAG CORRELATION ANALYSIS (INDUSTRY LEVEL)")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        # A. Shareholder change → Forward returns (PREDICTIVE)
        print("\n📊 A. Does Industry Shareholder Participation Change PREDICT Returns?")
        print("-"*80)
        
        predictive_results = []
        
        for lag_q in [1, 2, 4]:  # Shareholder participation metric
            for fwd_q in [1, 2, 4, 8]:  # Forward return horizon
                
                shareholder_col = f'pct_increasing_{lag_q}q'
                return_col = f'return_{fwd_q}q'
                
                valid_data = df.dropna(subset=[shareholder_col, return_col])
                valid_data = valid_data[
                    np.isfinite(valid_data[shareholder_col]) & 
                    np.isfinite(valid_data[return_col])
                ]
                
                if len(valid_data) < 30:
                    continue
                
                # Calculate correlation
                corr, pval = stats.pearsonr(
                    valid_data[shareholder_col],
                    valid_data[return_col]
                )
                
                predictive_results.append({
                    'shareholder_metric': f'{lag_q}Q % Increasing',
                    'return_forward': f'{fwd_q}Q',
                    'correlation': corr,
                    'p_value': pval,
                    'n_obs': len(valid_data),
                    'significant': 'Yes' if pval < 0.05 else 'No'
                })
                
                print(f"  Industry % Increasing ({lag_q}Q) → Returns (next {fwd_q}Q):")
                print(f"    Correlation: {corr:+.4f} | p-value: {pval:.4f} | "
                      f"n={len(valid_data):,} {'✅' if pval < 0.05 else '❌'}")
        
        pred_df = pd.DataFrame(predictive_results)
        
        # Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        best_pred = pred_df.loc[pred_df['correlation'].abs().idxmax()]
        
        print(f"\n🎯 Strongest Predictive Signal:")
        print(f"   {best_pred['shareholder_metric']} → Returns ({best_pred['return_forward']})")
        print(f"   Correlation: {best_pred['correlation']:+.4f}")
        print(f"   p-value: {best_pred['p_value']:.6f}")
        
        if best_pred['correlation'] < -0.05:
            print(f"\n   ✅ NEGATIVE correlation = CONTRARIAN signal works at INDUSTRY level!")
            print(f"      → Industries with LOW retail participation predict HIGHER returns")
            signal_quality = "STRONG" if abs(best_pred['correlation']) > 0.15 else "MODERATE" if abs(best_pred['correlation']) > 0.08 else "WEAK"
            print(f"      → Signal strength: {signal_quality}")
        elif best_pred['correlation'] > 0.05:
            print(f"\n   ❌ POSITIVE correlation = Momentum signal")
            print(f"      → Industries with HIGH retail participation predict HIGHER returns")
        else:
            print(f"\n   ⚠️  WEAK signal")
        
        # Save results
        self._save_correlation_results(pred_df)
        self._plot_correlation_heatmap(pred_df)
        
        return pred_df
    
    #########################################################################
    # STUDY 2: PERSISTENCE ANALYSIS
    #########################################################################
    
    def study_2_persistence_analysis(self):
        """Study 2: Persistence at industry level"""
        print("\n" + "="*80)
        print("STUDY 2: PERSISTENCE (DURATION) ANALYSIS (INDUSTRY LEVEL)")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        signal_col = 'pct_increasing_1q'
        
        print("\n📊 Bucketing industries by retail participation...")
        
        df_valid = df.dropna(subset=[signal_col])
        
        # Create quintiles (5 buckets - fewer industries than stocks)
        df_valid['participation_quintile'] = pd.qcut(
            df_valid[signal_col],
            q=5,
            labels=['Q1_Lowest', 'Q2', 'Q3', 'Q4', 'Q5_Highest'],
            duplicates='drop'
        )
        
        print("\n📈 Average Returns by Retail Participation Quintile:")
        print("-"*80)
        
        persistence_results = []
        
        for horizon in ['return_1q', 'return_2q', 'return_4q', 'return_8q']:
            if horizon not in df_valid.columns:
                continue
            
            avg_returns = df_valid.groupby('participation_quintile')[horizon].mean()
            
            if len(avg_returns) < 2:
                continue
            
            persistence_results.append({
                'horizon': horizon,
                'Q1_lowest': avg_returns.iloc[0] if len(avg_returns) > 0 else np.nan,
                'Q5_highest': avg_returns.iloc[-1] if len(avg_returns) > 0 else np.nan,
                'spread': avg_returns.iloc[0] - avg_returns.iloc[-1] if len(avg_returns) > 1 else np.nan
            })
            
            print(f"\n{horizon.upper()}:")
            print(f"  Q1 (Lowest Participation):   {avg_returns.iloc[0]:+7.2f}%")
            print(f"  Q5 (Highest Participation):  {avg_returns.iloc[-1]:+7.2f}%")
            print(f"  Spread (Q1 - Q5):            {avg_returns.iloc[0] - avg_returns.iloc[-1]:+7.2f}%")
            
            if avg_returns.iloc[0] > avg_returns.iloc[-1]:
                print(f"  ✅ Contrarian signal works at this horizon")
            else:
                print(f"  ❌ Momentum signal at this horizon")
        
        persist_df = pd.DataFrame(persistence_results)
        
        if len(persist_df) == 0:
            print("\n⚠️  Insufficient data")
            return persist_df
        
        # Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        max_spread = persist_df.loc[persist_df['spread'].abs().idxmax()]
        
        print(f"\n🎯 Optimal Holding Period:")
        print(f"   Horizon: {max_spread['horizon']}")
        print(f"   Spread: {max_spread['spread']:+.2f}%")
        
        if (persist_df['spread'] > 0).all():
            print(f"\n✅ Effect PERSISTS at all horizons")
            print(f"   → Contrarian signal has lasting power at INDUSTRY level")
        elif len(persist_df) > 1 and persist_df['spread'].iloc[0] > 0 and persist_df['spread'].iloc[-1] < 0:
            print(f"\n⚠️  Effect REVERSES over time")
        else:
            print(f"\n📊 Mixed results across horizons")
        
        # Save and plot
        self._save_persistence_results(persist_df, df_valid)
        self._plot_persistence_chart(df_valid)
        
        return persist_df
    
    #########################################################################
    # STUDY 3: MAGNITUDE ANALYSIS
    #########################################################################
    
    def study_3_magnitude_analysis(self):
        """Study 3: Magnitude analysis at industry level"""
        print("\n" + "="*80)
        print("STUDY 3: MAGNITUDE (SIZE EFFECT) ANALYSIS (INDUSTRY LEVEL)")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        signal_col = 'pct_increasing_1q'
        return_col = 'return_4q'
        
        df_valid = df.dropna(subset=[signal_col, return_col])
        
        print(f"\n📊 Analyzing {len(df_valid):,} industry-quarter observations...")
        
        print("\n📈 Returns by Retail Participation Level:")
        print("-"*80)
        
        # Define buckets
        buckets = [
            ('0-20% (Very Low)', lambda x: (x >= 0) & (x < 20)),
            ('20-40% (Low)', lambda x: (x >= 20) & (x < 40)),
            ('40-60% (Medium)', lambda x: (x >= 40) & (x < 60)),
            ('60-80% (High)', lambda x: (x >= 60) & (x < 80)),
            ('80-100% (Very High)', lambda x: (x >= 80) & (x <= 100))
        ]
        
        magnitude_results = []
        
        for bucket_name, bucket_filter in buckets:
            bucket_data = df_valid[bucket_filter(df_valid[signal_col])]
            
            if len(bucket_data) == 0:
                continue
            
            avg_return = bucket_data[return_col].mean()
            median_return = bucket_data[return_col].median()
            count = len(bucket_data)
            
            magnitude_results.append({
                'bucket': bucket_name,
                'avg_return': avg_return,
                'median_return': median_return,
                'count': count,
                'pct_of_total': count / len(df_valid) * 100
            })
            
            print(f"\n{bucket_name:25s} (n={count:4,}):")
            print(f"  Avg Return:    {avg_return:+7.2f}%")
            print(f"  Median Return: {median_return:+7.2f}%")
        
        mag_df = pd.DataFrame(magnitude_results)
        
        # Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        if len(mag_df) > 1:
            first_return = mag_df['avg_return'].iloc[0]
            last_return = mag_df['avg_return'].iloc[-1]
            
            if first_return > last_return:
                print(f"\n✅ MONOTONIC relationship: Lower participation → Better returns")
                print(f"   → Contrarian strategy validated at INDUSTRY level")
            else:
                print(f"\n❌ MOMENTUM relationship: Higher participation → Better returns")
        
        best_bucket = mag_df.loc[mag_df['avg_return'].idxmax()]
        print(f"\n🎯 Best Performing Bucket:")
        print(f"   {best_bucket['bucket']}: {best_bucket['avg_return']:+.2f}% avg return")
        print(f"   Represents {best_bucket['pct_of_total']:.1f}% of observations")
        
        # Save and plot
        self._save_magnitude_results(mag_df)
        self._plot_magnitude_chart(mag_df)
        
        return mag_df
    
    #########################################################################
    # HELPER METHODS
    #########################################################################
    
    def _save_correlation_results(self, pred_df):
        """Save correlation results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        pred_df.to_csv(
            output_dir / f'industry_study1_correlations_{timestamp}.csv',
            index=False
        )
        print(f"\n💾 Saved correlation results to: {output_dir}")
    
    def _plot_correlation_heatmap(self, pred_df):
        """Plot correlation heatmap"""
        heatmap_data = pred_df.pivot(
            index='shareholder_metric',
            columns='return_forward',
            values='correlation'
        )
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        sns.heatmap(
            heatmap_data,
            annot=True,
            fmt='.3f',
            cmap='RdYlGn',
            center=0,
            vmin=-0.5,
            vmax=0.5,
            cbar_kws={'label': 'Correlation'},
            ax=ax
        )
        
        ax.set_title('Industry Level: Retail Participation → Future Returns\n' +
                     '(Negative = Contrarian Signal)',
                     fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Forward Return Horizon', fontsize=11, fontweight='bold')
        ax.set_ylabel('Retail Participation Metric', fontsize=11, fontweight='bold')
        
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_study1_correlation_heatmap.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    def _save_persistence_results(self, persist_df, df_valid):
        """Save persistence results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        persist_df.to_csv(
            output_dir / f'industry_study2_persistence_{timestamp}.csv',
            index=False
        )
        print(f"\n💾 Saved persistence results to: {output_dir}")
    
    def _plot_persistence_chart(self, df_valid):
        """Plot persistence chart"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()
        
        horizons = ['return_1q', 'return_2q', 'return_4q', 'return_8q']
        titles = ['1 Quarter (3M)', '2 Quarters (6M)', '4 Quarters (1Y)', '8 Quarters (2Y)']
        
        for idx, (horizon, title) in enumerate(zip(horizons, titles)):
            if horizon not in df_valid.columns or 'participation_quintile' not in df_valid.columns:
                axes[idx].text(0.5, 0.5, 'Insufficient Data', 
                              ha='center', va='center', fontsize=14)
                axes[idx].set_title(f'Forward Returns: {title}', fontsize=12, fontweight='bold')
                continue
            
            avg_returns = df_valid.groupby('participation_quintile')[horizon].mean()
            
            if len(avg_returns) == 0:
                continue
            
            axes[idx].bar(range(len(avg_returns)), avg_returns.values, 
                         color=['green' if x > 0 else 'red' for x in avg_returns.values])
            axes[idx].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
            axes[idx].set_title(f'Forward Returns: {title}', fontsize=12, fontweight='bold')
            axes[idx].set_xlabel('Retail Participation Quintile', fontsize=10)
            axes[idx].set_ylabel('Average Return (%)', fontsize=10)
            axes[idx].set_xticks(range(len(avg_returns)))
            axes[idx].set_xticklabels(['Q1\n(Low)', 'Q2', 'Q3', 'Q4', 'Q5\n(High)'][:len(avg_returns)],
                                      fontsize=9)
            axes[idx].grid(axis='y', alpha=0.3)
            
            if len(avg_returns) > 1:
                spread = avg_returns.iloc[0] - avg_returns.iloc[-1]
                axes[idx].text(0.02, 0.98, f'Spread: {spread:+.2f}%',
                              transform=axes[idx].transAxes,
                              fontsize=10, fontweight='bold',
                              verticalalignment='top',
                              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle('Industry Level: Returns by Retail Participation Quintile',
                     fontsize=14, fontweight='bold', y=0.995)
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_study2_persistence_chart.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    def _save_magnitude_results(self, mag_df):
        """Save magnitude results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        mag_df.to_csv(
            output_dir / f'industry_study3_magnitude_{timestamp}.csv',
            index=False
        )
        print(f"\n💾 Saved magnitude results to: {output_dir}")
    
    def _plot_magnitude_chart(self, mag_df):
        """Plot magnitude chart"""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        x_pos = range(len(mag_df))
        colors = ['#2E7D32', '#66BB6A', '#FFB74D', '#FF8A65', '#E53935'][:len(mag_df)]
        
        bars = ax.bar(x_pos, mag_df['avg_return'], color=colors, alpha=0.7, edgecolor='black')
        
        for i, (bar, count) in enumerate(zip(bars, mag_df['count'])):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'n={count:,}',
                   ha='center', va='bottom' if height > 0 else 'top',
                   fontsize=9)
        
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_xlabel('Industry Retail Participation Level', fontsize=11, fontweight='bold')
        ax.set_ylabel('Average 1-Year Forward Return (%)', fontsize=11, fontweight='bold')
        ax.set_title('Industry Level: Returns by Retail Participation\n' +
                     '(Green = Low Participation, Red = High Participation)',
                     fontsize=13, fontweight='bold', pad=15)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(mag_df['bucket'], rotation=30, ha='right', fontsize=10)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_study3_magnitude_chart.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    #########################################################################
    # MASTER RUN METHOD
    #########################################################################
    
    def run_all_validation_studies(self):
        """Run all three validation studies"""
        print("\n" + "="*80)
        print("RUNNING ALL INDUSTRY-LEVEL VALIDATION STUDIES")
        print("="*80)
        
        # Calculate returns and changes
        self.calculate_industry_returns()
        self.calculate_industry_changes()
        
        # Run studies
        print("\n" + "🔬 " * 40)
        pred_df = self.study_1_lead_lag_correlation()
        
        print("\n" + "🔬 " * 40)
        persist_df = self.study_2_persistence_analysis()
        
        print("\n" + "🔬 " * 40)
        mag_df = self.study_3_magnitude_analysis()
        
        # Final summary
        self._print_final_summary(pred_df, persist_df, mag_df)
        
        return {
            'correlation': pred_df,
            'persistence': persist_df,
            'magnitude': mag_df,
            'analysis_df': self.analysis_df
        }
    
    def _print_final_summary(self, pred_df, persist_df, mag_df):
        """Print comprehensive summary"""
        print("\n" + "="*80)
        print("📋 FINAL VALIDATION SUMMARY - INDUSTRY LEVEL")
        print("="*80)
        
        # Study 1
        best_pred = pred_df.loc[pred_df['correlation'].abs().idxmax()]
        
        print("\n1️⃣  PREDICTIVE POWER (INDUSTRY LEVEL):")
        print(f"   Best Signal: {best_pred['shareholder_metric']} → {best_pred['return_forward']}")
        print(f"   Correlation: {best_pred['correlation']:+.4f}")
        print(f"   P-value: {best_pred['p_value']:.4f}")
        
        if abs(best_pred['correlation']) > 0.15:
            strength = "STRONG"
        elif abs(best_pred['correlation']) > 0.08:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        
        if best_pred['correlation'] < -0.05:
            print(f"   ✅ CONTRARIAN signal validated at INDUSTRY level")
            print(f"   → Signal strength: {strength}")
        elif best_pred['correlation'] > 0.05:
            print(f"   ❌ MOMENTUM signal found")
        else:
            print(f"   ⚠️  WEAK signal")
        
        # Study 2
        if len(persist_df) > 0:
            best_horizon = persist_df.loc[persist_df['spread'].abs().idxmax()]
            
            print(f"\n2️⃣  OPTIMAL HOLDING PERIOD:")
            print(f"   Horizon: {best_horizon['horizon']}")
            print(f"   Spread: {best_horizon['spread']:+.2f}%")
        
        # Study 3
        if len(mag_df) > 0:
            best_bucket = mag_df.loc[mag_df['avg_return'].idxmax()]
            
            print(f"\n3️⃣  SELECTION CRITERIA:")
            print(f"   Best Bucket: {best_bucket['bucket']}")
            print(f"   Avg Return: {best_bucket['avg_return']:+.2f}%")
        
        # Final verdict
        print("\n" + "="*80)
        print("🎯 RECOMMENDATION: INDUSTRY vs STOCK LEVEL")
        print("="*80)
        
        # Compare with stock-level (assuming stock-level correlation ~ 0.0016)
        if abs(best_pred['correlation']) > 0.05:
            print("\n✅ ✅ ✅  INDUSTRY-LEVEL IS SUPERIOR!")
            print(f"   Industry-level signal is MUCH CLEARER than stock-level")
            print(f"   Correlation: {best_pred['correlation']:+.4f} (industry) vs ~0.002 (stocks)")
            print(f"   → RECOMMEND: Industry-level strategy")
        else:
            print("\n⚠️ ⚠️ ⚠️  MIXED RESULTS")
            print(f"   Industry-level signal still weak")
            print(f"   → Consider alternative approaches or sector-level")
        
        print("\n" + "="*80)


def main():
    """Main execution function"""
    validator = IndustryContrarianValidator(min_stocks_per_industry=5)
    
    results = validator.run_all_validation_studies()
    
    print("\n" + "="*80)
    print("✅ INDUSTRY-LEVEL VALIDATION STUDIES COMPLETE")
    print("="*80)
    print("\nOutputs saved to:")
    print("  - Reports: analysis/outputs/reports/validation/")
    print("  - Charts:  analysis/outputs/charts/validation/")
    
    return validator, results


if __name__ == "__main__":
    validator, results = main()
