#!/usr/bin/env python
"""
Validation Studies for Contrarian Retail Interest Strategy

Tests whether declining retail participation (shareholder count) predicts
future stock/sector outperformance.

Three core studies:
1. Lead-Lag Correlation Analysis
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

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class ContrarianValidator:
    """Validate contrarian retail interest strategy hypothesis"""
    
    def __init__(self, base_path=None, universe='top1000'):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        self.universe = universe
        
        print("="*80)
        print("CONTRARIAN STRATEGY VALIDATION FRAMEWORK")
        print("="*80)
        print(f"Universe: {universe}")
        print(f"\nLoading data...")
        
        self._load_data()
        self._prepare_data()
    
    def _load_data(self):
        """Load required datasets"""
        # Shareholding patterns
        print("  Loading shareholding patterns...")
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv'
        )
        
        # Price data
        print("  Loading price data...")
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'company_name', 'date', 'close']
        )
        
        # Industry info
        print("  Loading industry info...")
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv'
        )
        
        print(f"\n  ✅ Loaded:")
        print(f"     - {len(self.shareholding_df):,} shareholding records")
        print(f"     - {len(self.price_df):,} price records")
        print(f"     - {len(self.industry_df):,} industry mappings")
    
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
    
    def _filter_universe(self):
        """Filter stocks based on universe selection"""
        print(f"\n  Filtering universe: {self.universe}...")
        
        if self.universe == 'top1000':
            # Get latest quarter from shareholding data
            shp_temp = self.shareholding_df.copy()
            shp_temp['quarter_date'] = shp_temp['quarter'].apply(self._parse_quarter_to_date)
            shp_temp = shp_temp.dropna(subset=['quarter_date'])
            latest_quarter = shp_temp['quarter_date'].max()
            
            # Get latest prices
            latest_prices = self.price_df.sort_values('date').groupby('isin').last().reset_index()
            
            # Get outstanding shares from latest quarter
            shp_quarter = shp_temp[shp_temp['quarter_date'] == latest_quarter][
                ['isin', 'total_outstanding_shares']
            ].copy()
            
            # Calculate market cap
            market_caps = latest_prices.merge(shp_quarter, on='isin', how='inner')
            market_caps['market_cap'] = market_caps['close'] * market_caps['total_outstanding_shares']
            
            # Get top 1000
            top_stocks = market_caps.nlargest(1000, 'market_cap')['isin'].tolist()
            
            print(f"     - Selected top 1000 stocks by market cap")
            print(f"     - Market cap range: ₹{market_caps['market_cap'].min()/1e7:.0f}Cr to ₹{market_caps['market_cap'].max()/1e7:.0f}Cr")
            
        elif self.universe == 'top500':
            shp_temp = self.shareholding_df.copy()
            shp_temp['quarter_date'] = shp_temp['quarter'].apply(self._parse_quarter_to_date)
            shp_temp = shp_temp.dropna(subset=['quarter_date'])
            latest_quarter = shp_temp['quarter_date'].max()
            
            latest_prices = self.price_df.sort_values('date').groupby('isin').last().reset_index()
            shp_quarter = shp_temp[shp_temp['quarter_date'] == latest_quarter][
                ['isin', 'total_outstanding_shares']
            ].copy()
            
            market_caps = latest_prices.merge(shp_quarter, on='isin', how='inner')
            market_caps['market_cap'] = market_caps['close'] * market_caps['total_outstanding_shares']
            top_stocks = market_caps.nlargest(500, 'market_cap')['isin'].tolist()
            
        elif self.universe == 'all':
            top_stocks = self.shareholding_df['isin'].unique().tolist()
            
        else:
            raise ValueError(f"Unknown universe: {self.universe}")
        
        # Filter all dataframes
        self.shareholding_df = self.shareholding_df[
            self.shareholding_df['isin'].isin(top_stocks)
        ]
        self.price_df = self.price_df[
            self.price_df['isin'].isin(top_stocks)
        ]
        
        print(f"     - Filtered to {len(top_stocks):,} stocks")
        
        return top_stocks
    
    def _prepare_data(self):
        """Prepare and merge all data"""
        print("\n  Preparing data...")
        
        # Filter universe
        self._filter_universe()
        
        # Parse dates
        print("     - Parsing quarter dates...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        self.shareholding_df = self.shareholding_df.dropna(
            subset=['quarter_date', 'total_shareholders']
        )
        self.shareholding_df = self.shareholding_df[
            self.shareholding_df['total_shareholders'] > 0
        ]
        
        # Merge with industry
        self.shareholding_df = self.shareholding_df.merge(
            self.industry_df[['isin', 'industry', 'industry_group']],
            on='isin',
            how='left'
        )
        
        # Sort
        self.shareholding_df = self.shareholding_df.sort_values(['isin', 'quarter_date'])
        
        # Parse price dates
        print("     - Parsing price dates...")
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"\n  ✅ Data prepared:")
        print(f"     - Valid shareholding records: {len(self.shareholding_df):,}")
        print(f"     - Date range: {self.shareholding_df['quarter_date'].min().date()} to {self.shareholding_df['quarter_date'].max().date()}")
        print(f"     - Unique stocks: {self.shareholding_df['isin'].nunique():,}")
        print(f"     - Price records: {len(self.price_df):,}")
    
    def calculate_quarterly_returns(self):
        """Calculate forward returns for each quarter"""
        print("\n  Calculating quarterly forward returns...")
        
        # Get unique quarters
        quarters = sorted(self.shareholding_df['quarter_date'].unique())
        
        # For each stock & quarter, calculate forward returns
        results = []
        
        total_stocks = self.shareholding_df['isin'].nunique()
        processed = 0
        
        for isin in self.shareholding_df['isin'].unique():
            processed += 1
            if processed % 100 == 0:
                print(f"     Processing {processed}/{total_stocks}...", end='\r')
            
            stock_shp = self.shareholding_df[
                self.shareholding_df['isin'] == isin
            ].copy()
            stock_price = self.price_df[
                self.price_df['isin'] == isin
            ].copy()
            
            if len(stock_price) == 0:
                continue
            
            for _, row in stock_shp.iterrows():
                quarter_date = row['quarter_date']
                
                # Get price on quarter end date (or closest after)
                price_at_quarter = stock_price[
                    stock_price['date'] >= quarter_date
                ].head(1)
                
                if len(price_at_quarter) == 0:
                    continue
                
                price_0q = price_at_quarter['close'].iloc[0]
                date_0q = price_at_quarter['date'].iloc[0]
                
                result = {
                    'isin': isin,
                    'company_name': row['company_name'],
                    'quarter_date': quarter_date,
                    'total_shareholders': row['total_shareholders'],
                    'industry': row['industry'],
                    'industry_group': row['industry_group']
                }
                
                # Calculate forward returns at different horizons
                for quarters_forward in [1, 2, 4, 8]:
                    target_date = quarter_date + pd.DateOffset(months=3*quarters_forward)
                    
                    price_forward = stock_price[
                        stock_price['date'] >= target_date
                    ].head(1)
                    
                    if len(price_forward) > 0:
                        price_fwd = price_forward['close'].iloc[0]
                        ret = (price_fwd / price_0q - 1) * 100
                        
                        # Cap extreme returns to prevent infinite values
                        if abs(ret) > 10000:  # Cap at ±10,000%
                            ret = np.sign(ret) * 10000
                        
                        result[f'return_{quarters_forward}q'] = ret
                    else:
                        result[f'return_{quarters_forward}q'] = np.nan
                
                results.append(result)
        
        print(f"     ✅ Calculated returns for {len(results):,} observations" + " "*20)
        
        self.returns_df = pd.DataFrame(results)
        return self.returns_df
    
    def calculate_shareholder_changes(self):
        """Calculate quarter-over-quarter changes in shareholder count"""
        print("\n  Calculating shareholder changes...")
        
        df = self.returns_df.copy()
        df = df.sort_values(['isin', 'quarter_date'])
        
        # Calculate 1Q, 2Q, 4Q changes
        for lag in [1, 2, 4]:
            df[f'shareholders_{lag}q_ago'] = df.groupby('isin')['total_shareholders'].shift(lag)
            df[f'change_{lag}q_pct'] = (
                (df['total_shareholders'] - df[f'shareholders_{lag}q_ago']) / 
                df[f'shareholders_{lag}q_ago'] * 100
            )
        
        # Remove first observations without historical data
        df = df.dropna(subset=['shareholders_1q_ago'])
        
        print(f"     ✅ Calculated changes for {len(df):,} observations")
        
        self.analysis_df = df
        return df
    
    #########################################################################
    # STUDY 1: LEAD-LAG CORRELATION ANALYSIS
    #########################################################################
    
    def study_1_lead_lag_correlation(self):
        """
        Study 1: Lead-Lag Correlation Analysis
        
        Question: Does shareholder change PREDICT returns or FOLLOW them?
        
        Tests:
        - Shareholder change (Q0) vs Returns (Q+1, Q+2, Q+4, Q+8)
        - Returns (Q0) vs Shareholder change (Q+1, Q+2, Q+4)
        """
        print("\n" + "="*80)
        print("STUDY 1: LEAD-LAG CORRELATION ANALYSIS")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        # A. Shareholder change → Forward returns (PREDICTIVE)
        print("\n📊 A. Does Shareholder Change PREDICT Future Returns?")
        print("-"*80)
        
        predictive_results = []
        
        for lag_q in [1, 2, 4]:  # Shareholder change lookback
            for fwd_q in [1, 2, 4, 8]:  # Forward return horizon
                
                shareholder_col = f'change_{lag_q}q_pct'
                return_col = f'return_{fwd_q}q'
                
                valid_data = df.dropna(subset=[shareholder_col, return_col])
                
                # Remove infinite values
                valid_data = valid_data[
                    np.isfinite(valid_data[shareholder_col]) & 
                    np.isfinite(valid_data[return_col])
                ]
                
                if len(valid_data) < 100:
                    continue
                
                # Calculate correlation
                corr, pval = stats.pearsonr(
                    valid_data[shareholder_col],
                    valid_data[return_col]
                )
                
                predictive_results.append({
                    'shareholder_lookback': f'{lag_q}Q',
                    'return_forward': f'{fwd_q}Q',
                    'correlation': corr,
                    'p_value': pval,
                    'n_obs': len(valid_data),
                    'significant': 'Yes' if pval < 0.05 else 'No'
                })
                
                print(f"  Shareholder Δ (past {lag_q}Q) → Returns (next {fwd_q}Q):")
                print(f"    Correlation: {corr:+.4f} | p-value: {pval:.4f} | "
                      f"n={len(valid_data):,} {'✅' if pval < 0.05 else '❌'}")
        
        pred_df = pd.DataFrame(predictive_results)
        
        # B. Returns → Future shareholder changes (FOLLOWING)
        print("\n📊 B. Do Returns LEAD Shareholder Changes? (Noise/Following)")
        print("-"*80)
        
        following_results = []
        
        # Calculate backward returns
        for ret_lookback in [1, 2, 4]:
            df[f'past_return_{ret_lookback}q'] = df.groupby('isin')[f'return_{ret_lookback}q'].shift(ret_lookback)
        
        for ret_lag in [1, 2, 4]:
            for shp_fwd in [1, 2]:
                
                return_col = f'past_return_{ret_lag}q'
                shareholder_col = f'change_{shp_fwd}q_pct'
                
                valid_data = df.dropna(subset=[return_col, shareholder_col])
                
                # Remove infinite values
                valid_data = valid_data[
                    np.isfinite(valid_data[return_col]) & 
                    np.isfinite(valid_data[shareholder_col])
                ]
                
                if len(valid_data) < 100:
                    continue
                
                corr, pval = stats.pearsonr(
                    valid_data[return_col],
                    valid_data[shareholder_col]
                )
                
                following_results.append({
                    'return_lookback': f'{ret_lag}Q',
                    'shareholder_forward': f'{shp_fwd}Q',
                    'correlation': corr,
                    'p_value': pval,
                    'n_obs': len(valid_data),
                    'significant': 'Yes' if pval < 0.05 else 'No'
                })
                
                print(f"  Returns (past {ret_lag}Q) → Shareholder Δ (next {shp_fwd}Q):")
                print(f"    Correlation: {corr:+.4f} | p-value: {pval:.4f} | "
                      f"n={len(valid_data):,} {'✅' if pval < 0.05 else '❌'}")
        
        follow_df = pd.DataFrame(following_results)
        
        # C. Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        # Find strongest predictive signal
        best_pred = pred_df.loc[pred_df['correlation'].abs().idxmax()]
        
        print(f"\n🎯 Strongest Predictive Signal:")
        print(f"   Shareholder change (past {best_pred['shareholder_lookback']}) → "
              f"Returns (next {best_pred['return_forward']})")
        print(f"   Correlation: {best_pred['correlation']:+.4f}")
        print(f"   p-value: {best_pred['p_value']:.6f}")
        
        if best_pred['correlation'] < 0:
            print(f"\n   ✅ NEGATIVE correlation = CONTRARIAN signal works!")
            print(f"      → Declining shareholders predict HIGHER returns")
            signal_quality = "STRONG" if abs(best_pred['correlation']) > 0.1 else "WEAK"
            print(f"      → Signal strength: {signal_quality}")
        else:
            print(f"\n   ❌ POSITIVE correlation = Momentum signal")
            print(f"      → Increasing shareholders predict HIGHER returns")
            print(f"      → Contrarian strategy NOT supported by data")
        
        # Check if returns lead shareholder changes (noise)
        if len(follow_df) > 0:
            best_follow = follow_df.loc[follow_df['correlation'].abs().idxmax()]
            print(f"\n📊 Strongest Following Signal:")
            print(f"   Returns (past {best_follow['return_lookback']}) → "
                  f"Shareholder Δ (next {best_follow['shareholder_forward']})")
            print(f"   Correlation: {best_follow['correlation']:+.4f}")
            
            if abs(best_follow['correlation']) > abs(best_pred['correlation']):
                print(f"\n   ⚠️  WARNING: Returns LEAD shareholder changes more than reverse")
                print(f"      → Shareholder changes may be NOISE, not signal")
            else:
                print(f"\n   ✅ Shareholder changes are more predictive than reactive")
        
        # Save results
        self._save_correlation_results(pred_df, follow_df)
        
        # Visualize
        self._plot_correlation_heatmap(pred_df)
        
        return pred_df, follow_df
    
    #########################################################################
    # STUDY 2: PERSISTENCE ANALYSIS
    #########################################################################
    
    def study_2_persistence_analysis(self):
        """
        Study 2: Persistence Analysis
        
        Question: How long does the contrarian effect last?
        
        Tests returns at 1Q, 2Q, 4Q, 8Q horizons after shareholder decline
        """
        print("\n" + "="*80)
        print("STUDY 2: PERSISTENCE (DURATION) ANALYSIS")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        # Use 1Q shareholder change as the signal
        signal_col = 'change_1q_pct'
        
        # Bucket stocks by shareholder change
        print("\n📊 Bucketing stocks by shareholder change...")
        
        df_valid = df.dropna(subset=[signal_col])
        
        # Create deciles
        df_valid['shareholder_decile'] = pd.qcut(
            df_valid[signal_col],
            q=10,
            labels=['D1_Biggest_Decline', 'D2', 'D3', 'D4', 'D5', 
                    'D6', 'D7', 'D8', 'D9', 'D10_Biggest_Increase'],
            duplicates='drop'
        )
        
        # Calculate average returns by decile for each horizon
        print("\n📈 Average Returns by Shareholder Change Decile:")
        print("-"*80)
        
        persistence_results = []
        
        for horizon in ['return_1q', 'return_2q', 'return_4q', 'return_8q']:
            if horizon not in df_valid.columns:
                continue
            
            avg_returns = df_valid.groupby('shareholder_decile')[horizon].mean()
            
            if len(avg_returns) < 2:
                continue
            
            persistence_results.append({
                'horizon': horizon,
                'D1_decline': avg_returns.iloc[0] if len(avg_returns) > 0 else np.nan,
                'D10_increase': avg_returns.iloc[-1] if len(avg_returns) > 0 else np.nan,
                'spread': avg_returns.iloc[0] - avg_returns.iloc[-1] if len(avg_returns) > 1 else np.nan
            })
            
            print(f"\n{horizon.upper()}:")
            print(f"  D1 (Biggest Decline):   {avg_returns.iloc[0]:+7.2f}%")
            print(f"  D10 (Biggest Increase): {avg_returns.iloc[-1]:+7.2f}%")
            print(f"  Spread (D1 - D10):      {avg_returns.iloc[0] - avg_returns.iloc[-1]:+7.2f}%")
            
            if avg_returns.iloc[0] > avg_returns.iloc[-1]:
                print(f"  ✅ Contrarian signal works at this horizon")
            else:
                print(f"  ❌ Momentum signal at this horizon")
        
        persist_df = pd.DataFrame(persistence_results)
        
        if len(persist_df) == 0:
            print("\n⚠️  Insufficient data for persistence analysis")
            return persist_df
        
        # Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        max_spread = persist_df.loc[persist_df['spread'].abs().idxmax()]
        
        print(f"\n🎯 Optimal Holding Period:")
        print(f"   Horizon: {max_spread['horizon']}")
        print(f"   Spread: {max_spread['spread']:+.2f}%")
        
        # Check if effect persists or reverses
        if len(persist_df) > 1:
            if persist_df['spread'].iloc[0] > 0 and persist_df['spread'].iloc[-1] < 0:
                print(f"\n⚠️  Effect REVERSES over time")
                print(f"   → Short-term contrarian, long-term mean reversion")
            elif (persist_df['spread'] > 0).all():
                print(f"\n✅ Effect PERSISTS at all horizons")
                print(f"   → Contrarian signal has lasting power")
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
        """
        Study 3: Magnitude Analysis
        
        Question: Does the SIZE of shareholder change matter?
        
        Tests if larger declines → better returns (non-linear relationship)
        """
        print("\n" + "="*80)
        print("STUDY 3: MAGNITUDE (SIZE EFFECT) ANALYSIS")
        print("="*80)
        
        df = self.analysis_df.copy()
        
        signal_col = 'change_1q_pct'
        return_col = 'return_4q'  # Use 1-year forward return
        
        df_valid = df.dropna(subset=[signal_col, return_col])
        
        print(f"\n📊 Analyzing {len(df_valid):,} observations...")
        
        # Create buckets by magnitude of change
        print("\n📈 Returns by Magnitude of Shareholder Change:")
        print("-"*80)
        
        # Define buckets
        buckets = [
            ('< -50%', lambda x: x < -50),
            ('-50% to -20%', lambda x: (x >= -50) & (x < -20)),
            ('-20% to -10%', lambda x: (x >= -20) & (x < -10)),
            ('-10% to 0%', lambda x: (x >= -10) & (x < 0)),
            ('0% to +10%', lambda x: (x >= 0) & (x < 10)),
            ('+10% to +20%', lambda x: (x >= 10) & (x < 20)),
            ('+20% to +50%', lambda x: (x >= 20) & (x < 50)),
            ('> +50%', lambda x: x >= 50)
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
            
            print(f"\n{bucket_name:20s} (n={count:5,}):")
            print(f"  Avg Return:    {avg_return:+7.2f}%")
            print(f"  Median Return: {median_return:+7.2f}%")
        
        mag_df = pd.DataFrame(magnitude_results)
        
        # Interpretation
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        
        # Check if returns increase with decline magnitude
        decline_buckets = mag_df[mag_df['bucket'].str.contains('<|to -')]
        if len(decline_buckets) > 1:
            # Check if generally increasing
            first_return = decline_buckets['avg_return'].iloc[0]
            last_return = decline_buckets['avg_return'].iloc[-1]
            
            if first_return > last_return:
                print(f"\n✅ Generally positive relationship: Bigger declines → Better returns")
                print(f"   → Use top X% of declining stocks")
            else:
                print(f"\n⚠️  NON-MONOTONIC relationship")
                print(f"   → Sweet spot may exist (not all declines are equal)")
        
        # Find best bucket
        best_bucket = mag_df.loc[mag_df['avg_return'].idxmax()]
        print(f"\n🎯 Best Performing Bucket:")
        print(f"   {best_bucket['bucket']}: {best_bucket['avg_return']:+.2f}% avg return")
        print(f"   Represents {best_bucket['pct_of_total']:.1f}% of observations")
        
        # Save and plot
        self._save_magnitude_results(mag_df)
        self._plot_magnitude_chart(mag_df)
        
        return mag_df
    
    #########################################################################
    # HELPER METHODS - SAVING & PLOTTING
    #########################################################################
    
    def _save_correlation_results(self, pred_df, follow_df):
        """Save correlation analysis results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        pred_df.to_csv(
            output_dir / f'study1_predictive_correlations_{timestamp}.csv',
            index=False
        )
        follow_df.to_csv(
            output_dir / f'study1_following_correlations_{timestamp}.csv',
            index=False
        )
        
        print(f"\n💾 Saved correlation results to: {output_dir}")
    
    def _plot_correlation_heatmap(self, pred_df):
        """Plot correlation heatmap"""
        # Pivot for heatmap
        heatmap_data = pred_df.pivot(
            index='shareholder_lookback',
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
            vmin=-0.3,
            vmax=0.3,
            cbar_kws={'label': 'Correlation'},
            ax=ax
        )
        
        ax.set_title('Lead-Lag Correlation: Shareholder Change → Future Returns\n' +
                     '(Negative = Contrarian Signal)',
                     fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Forward Return Horizon', fontsize=11, fontweight='bold')
        ax.set_ylabel('Shareholder Change Lookback', fontsize=11, fontweight='bold')
        
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'study1_correlation_heatmap.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    def _save_persistence_results(self, persist_df, df_valid):
        """Save persistence analysis results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        persist_df.to_csv(
            output_dir / f'study2_persistence_summary_{timestamp}.csv',
            index=False
        )
        
        # Also save decile-level details
        for horizon in ['return_1q', 'return_2q', 'return_4q', 'return_8q']:
            if horizon in df_valid.columns and 'shareholder_decile' in df_valid.columns:
                decile_stats = df_valid.groupby('shareholder_decile')[horizon].agg([
                    'mean', 'median', 'std', 'count'
                ])
                decile_stats.to_csv(
                    output_dir / f'study2_persistence_{horizon}_{timestamp}.csv'
                )
        
        print(f"\n💾 Saved persistence results to: {output_dir}")
    
    def _plot_persistence_chart(self, df_valid):
        """Plot persistence chart"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        axes = axes.flatten()
        
        horizons = ['return_1q', 'return_2q', 'return_4q', 'return_8q']
        titles = ['1 Quarter (3M)', '2 Quarters (6M)', '4 Quarters (1Y)', '8 Quarters (2Y)']
        
        for idx, (horizon, title) in enumerate(zip(horizons, titles)):
            if horizon not in df_valid.columns or 'shareholder_decile' not in df_valid.columns:
                axes[idx].text(0.5, 0.5, 'Insufficient Data', 
                              ha='center', va='center', fontsize=14)
                axes[idx].set_title(f'Forward Returns: {title}', fontsize=12, fontweight='bold')
                continue
            
            avg_returns = df_valid.groupby('shareholder_decile')[horizon].mean()
            
            if len(avg_returns) == 0:
                continue
            
            axes[idx].bar(range(len(avg_returns)), avg_returns.values, 
                         color=['green' if x > 0 else 'red' for x in avg_returns.values])
            axes[idx].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
            axes[idx].set_title(f'Forward Returns: {title}', fontsize=12, fontweight='bold')
            axes[idx].set_xlabel('Shareholder Change Decile', fontsize=10)
            axes[idx].set_ylabel('Average Return (%)', fontsize=10)
            axes[idx].set_xticks(range(len(avg_returns)))
            axes[idx].set_xticklabels(['D1\n(Decline)', 'D2', 'D3', 'D4', 'D5',
                                       'D6', 'D7', 'D8', 'D9', 'D10\n(Increase)'][:len(avg_returns)],
                                      fontsize=8)
            axes[idx].grid(axis='y', alpha=0.3)
            
            # Add spread annotation
            if len(avg_returns) > 1:
                spread = avg_returns.iloc[0] - avg_returns.iloc[-1]
                axes[idx].text(0.02, 0.98, f'Spread: {spread:+.2f}%',
                              transform=axes[idx].transAxes,
                              fontsize=10, fontweight='bold',
                              verticalalignment='top',
                              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle('Persistence Analysis: Returns by Shareholder Change Decile Across Horizons',
                     fontsize=14, fontweight='bold', y=0.995)
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'study2_persistence_chart.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    def _save_magnitude_results(self, mag_df):
        """Save magnitude analysis results"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        mag_df.to_csv(
            output_dir / f'study3_magnitude_analysis_{timestamp}.csv',
            index=False
        )
        
        print(f"\n💾 Saved magnitude results to: {output_dir}")
    
    def _plot_magnitude_chart(self, mag_df):
        """Plot magnitude chart"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        x_pos = range(len(mag_df))
        colors = ['darkgreen' if '<' in b or 'to -' in b else 'darkred' 
                 for b in mag_df['bucket']]
        
        bars = ax.bar(x_pos, mag_df['avg_return'], color=colors, alpha=0.7, edgecolor='black')
        
        # Add count labels on bars
        for i, (bar, count) in enumerate(zip(bars, mag_df['count'])):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'n={count:,}',
                   ha='center', va='bottom' if height > 0 else 'top',
                   fontsize=8)
        
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_xlabel('Shareholder Change Magnitude', fontsize=11, fontweight='bold')
        ax.set_ylabel('Average 1-Year Forward Return (%)', fontsize=11, fontweight='bold')
        ax.set_title('Magnitude Analysis: Returns by Size of Shareholder Change\n' +
                     '(Green = Declining Shareholders, Red = Increasing Shareholders)',
                     fontsize=13, fontweight='bold', pad=15)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(mag_df['bucket'], rotation=45, ha='right', fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts' / 'validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'study3_magnitude_chart.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"📊 Saved chart: {output_path}")
        
        plt.close()
    
    #########################################################################
    # MASTER RUN METHOD
    #########################################################################
    
    def run_all_validation_studies(self):
        """Run all three validation studies"""
        print("\n" + "="*80)
        print("RUNNING ALL VALIDATION STUDIES")
        print("="*80)
        
        # Calculate returns and changes
        self.calculate_quarterly_returns()
        self.calculate_shareholder_changes()
        
        # Run studies
        print("\n" + "🔬 " * 40)
        pred_df, follow_df = self.study_1_lead_lag_correlation()
        
        print("\n" + "🔬 " * 40)
        persist_df = self.study_2_persistence_analysis()
        
        print("\n" + "🔬 " * 40)
        mag_df = self.study_3_magnitude_analysis()
        
        # Final summary
        self._print_final_summary(pred_df, persist_df, mag_df)
        
        return {
            'correlation': (pred_df, follow_df),
            'persistence': persist_df,
            'magnitude': mag_df,
            'analysis_df': self.analysis_df
        }
    
    def _print_final_summary(self, pred_df, persist_df, mag_df):
        """Print comprehensive summary"""
        print("\n" + "="*80)
        print("📋 FINAL VALIDATION SUMMARY")
        print("="*80)
        
        # Study 1
        best_pred = pred_df.loc[pred_df['correlation'].abs().idxmax()]
        
        print("\n1️⃣  PREDICTIVE POWER:")
        print(f"   Best Signal: Shareholder Δ ({best_pred['shareholder_lookback']}) → "
              f"Returns ({best_pred['return_forward']})")
        print(f"   Correlation: {best_pred['correlation']:+.4f}")
        
        if best_pred['correlation'] < -0.05:
            print(f"   ✅ CONTRARIAN signal validated")
            print(f"   → Strategy: BUY declining shareholder stocks")
        elif best_pred['correlation'] > 0.05:
            print(f"   ❌ MOMENTUM signal found")
            print(f"   → Contrarian hypothesis REJECTED")
        else:
            print(f"   ⚠️  WEAK signal - needs further investigation")
        
        # Study 2
        if len(persist_df) > 0:
            best_horizon = persist_df.loc[persist_df['spread'].abs().idxmax()]
            
            print(f"\n2️⃣  OPTIMAL HOLDING PERIOD:")
            print(f"   Horizon: {best_horizon['horizon']}")
            print(f"   Spread: {best_horizon['spread']:+.2f}%")
            print(f"   → Recommendation: Hold for {best_horizon['horizon'].replace('return_', '').replace('q', ' quarters')}")
        
        # Study 3
        if len(mag_df) > 0:
            best_bucket = mag_df.loc[mag_df['avg_return'].idxmax()]
            
            print(f"\n3️⃣  SELECTION CRITERIA:")
            print(f"   Best Bucket: {best_bucket['bucket']}")
            print(f"   Avg Return: {best_bucket['avg_return']:+.2f}%")
            print(f"   → Recommendation: Focus on stocks in this range")
        
        # Final verdict
        print("\n" + "="*80)
        print("🎯 GO/NO-GO DECISION")
        print("="*80)
        
        if best_pred['correlation'] < -0.05 and best_pred['p_value'] < 0.05:
            print("\n✅ ✅ ✅  PROCEED TO BACKTESTING")
            print(f"   Contrarian strategy shows statistically significant predictive power")
            print(f"   Expected edge: {abs(best_pred['correlation'])*100:.1f}% correlation strength")
        else:
            print("\n❌ ❌ ❌  DO NOT PROCEED")
            print(f"   Contrarian hypothesis not supported by data")
            print(f"   Consider alternative strategies")
        
        print("\n" + "="*80)


def main():
    """Main execution function"""
    # Run validator
    validator = ContrarianValidator(universe='all')
    
    # Run all studies
    results = validator.run_all_validation_studies()
    
    print("\n" + "="*80)
    print("✅ VALIDATION STUDIES COMPLETE")
    print("="*80)
    print("\nOutputs saved to:")
    print("  - Reports: analysis/outputs/reports/validation/")
    print("  - Charts:  analysis/outputs/charts/validation/")
    
    return validator, results


if __name__ == "__main__":
    validator, results = main()
