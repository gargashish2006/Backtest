#!/usr/bin/env python
"""
Industry Selection Validation Analysis (OPTIMIZED)

Validates industry selection signals across multiple lookback and holding periods:
- Lookback: 1Q, 2Q, 4Q, 8Q, 12Q (36 months)
- Holding: 90 days, 180 days, 365 days
- Methods: Pure Contrarian vs Trend-Filtered
- Groups: Bottom 10 vs Top 10 industries

Uses industry benchmark returns from analysis/outputs/industry/

Optimizations:
- Pre-compute shareholding changes for all lookback periods
- Pre-compute 200-day MA for all stocks
- Vectorized operations instead of iterrows()
- Cache industry metrics by date
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class IndustrySelectionValidation:
    """
    Validate industry selection across multiple lookback and holding periods
    """
    
    def __init__(self):
        print("="*100)
        print("INDUSTRY SELECTION VALIDATION ANALYSIS (OPTIMIZED)")
        print("="*100)
        print("\nLoading and pre-processing data...")
        
        self.base_path = Path(__file__).parent.parent
        self.database_path = self.base_path / 'database'
        
        # Load data
        print("  Loading price data...")
        self.price_df = pd.read_parquet(self.database_path / 'price_data.parquet')
        print("  Loading shareholding data...")
        self.shp_df = pd.read_parquet(self.database_path / 'shareholding_patterns.parquet')
        print("  Loading industry info...")
        self.industry_df = pd.read_parquet(self.database_path / 'industry_info.parquet')
        
        # Parse shareholding quarters
        print("  Parsing quarter dates...")
        self.shp_df['quarter_date'] = self.shp_df['quarter'].apply(self.parse_quarter_to_date)
        
        # PRE-COMPUTE: Merge shareholding with industry once
        print("  Pre-computing industry mappings...")
        self.shp_with_industry = self._precompute_shp_industry_merge()
        
        # PRE-COMPUTE: Shareholding changes for all lookback periods
        print("  Pre-computing shareholding changes for all lookback periods...")
        self.lookback_changes = self._precompute_lookback_changes([1, 2, 4, 8, 12])
        
        # PRE-COMPUTE: 200-day moving averages
        print("  Pre-computing 200-day moving averages...")
        self.stock_ma_data = self._precompute_moving_averages()
        
        # Load industry benchmarks
        print("  Loading industry benchmarks...")
        self.industry_returns = self.load_industry_benchmarks()
        
        # Cache for metrics
        self._sh_metrics_cache = {}
        self._trend_metrics_cache = {}
        
        print(f"\n✅ Data loaded and pre-processed successfully")
        print(f"   Shareholding records: {len(self.shp_df):,}")
        print(f"   Price records: {len(self.price_df):,}")
        print(f"   Industry benchmarks: {len(self.industry_returns)}")
    
    def _precompute_shp_industry_merge(self):
        """Pre-merge shareholding with industry info (done once)"""
        data = self.shp_df.merge(
            self.industry_df[['isin', 'industry']],
            on='isin',
            how='left'
        )
        data = data.dropna(subset=['quarter_date', 'total_shareholders', 'industry'])
        data = data[data['total_shareholders'] > 0]
        data = data[data['industry'] != 'Not Available']
        data = data.sort_values(['isin', 'quarter_date'])
        return data
    
    def _precompute_lookback_changes(self, lookbacks):
        """Pre-compute shareholding changes for all lookback periods using vectorized shift"""
        changes = {}
        data = self.shp_with_industry.copy()
        
        for lb in lookbacks:
            # Use shift to get previous shareholders (vectorized)
            data[f'prev_sh_{lb}'] = data.groupby('isin')['total_shareholders'].shift(lb)
            data[f'change_{lb}'] = data['total_shareholders'] - data[f'prev_sh_{lb}']
            data[f'decreasing_{lb}'] = data[f'change_{lb}'] < 0
        
        self.shp_with_industry = data
        return lookbacks
    
    def _precompute_moving_averages(self):
        """Pre-compute 200-day MA for all stocks"""
        prices = self.price_df.sort_values(['isin', 'date']).copy()
        prices['ma_200'] = prices.groupby('isin')['close'].transform(
            lambda x: x.rolling(200, min_periods=150).mean()
        )
        prices['above_ma'] = prices['close'] > prices['ma_200']
        return prices
    
    def parse_quarter_to_date(self, quarter_str):
        """Parse quarter string to date"""
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
    
    def load_industry_benchmarks(self):
        """Load industry benchmark files"""
        industry_path = self.base_path / 'analysis' / 'outputs' / 'benchmarks' / 'industries'
        
        benchmarks = {}
        for industry_dir in industry_path.iterdir():
            if not industry_dir.is_dir():
                continue
            
            industry_name = industry_dir.name
            timeseries_file = industry_dir / 'timeseries.parquet'
            
            if not timeseries_file.exists():
                continue
            
            try:
                df = pd.read_parquet(timeseries_file)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                # Rename index_value to close for consistency
                if 'index_value' in df.columns:
                    df['close'] = df['index_value']
                benchmarks[industry_name] = df
            except Exception as e:
                continue
        
        return benchmarks
    
    def calculate_industry_shareholding_metrics(self, date, lookback_quarters):
        """
        Calculate % stocks with decreasing shareholders per industry (OPTIMIZED)
        Uses pre-computed lookback changes
        
        Args:
            date: As-of date
            lookback_quarters: Number of quarters to look back (1, 2, 4, 8, 12)
        """
        cache_key = (date, lookback_quarters)
        if cache_key in self._sh_metrics_cache:
            return self._sh_metrics_cache[cache_key]
        
        data = self.shp_with_industry
        
        # Get recent data (within 90 days of target date)
        cutoff_date = date - pd.Timedelta(days=90)
        recent = data[
            (data['quarter_date'] >= cutoff_date) &
            (data['quarter_date'] <= date)
        ].copy()
        
        # Get latest record per stock
        recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()
        
        # Use pre-computed change column
        change_col = f'decreasing_{lookback_quarters}'
        prev_col = f'prev_sh_{lookback_quarters}'
        
        # Filter stocks with valid lookback
        valid = recent[recent[prev_col].notna()].copy()
        
        if len(valid) == 0:
            return pd.DataFrame()
        
        # Group by industry (vectorized aggregation)
        industry_metrics = valid.groupby('industry').agg(
            total_stocks=('isin', 'count'),
            decreasing_stocks=(change_col, 'sum')
        ).reset_index()
        
        industry_metrics['pct_decreasing'] = (
            industry_metrics['decreasing_stocks'] / industry_metrics['total_stocks'] * 100
        )
        
        # Filter industries with at least 5 stocks
        industry_metrics = industry_metrics[industry_metrics['total_stocks'] >= 5]
        
        self._sh_metrics_cache[cache_key] = industry_metrics
        return industry_metrics
    
    def calculate_industry_trend_metrics(self, date):
        """Calculate % stocks above 200-day MA per industry (OPTIMIZED)
        Uses pre-computed moving averages"""
        
        if date in self._trend_metrics_cache:
            return self._trend_metrics_cache[date]
        
        # Use pre-computed MA data - just filter to date
        prices = self.stock_ma_data[self.stock_ma_data['date'] <= date]
        
        if len(prices) == 0:
            return pd.DataFrame()
        
        # Get latest price per stock
        latest = prices.groupby('isin').last().reset_index()
        
        # Merge with industry
        latest = latest.merge(
            self.industry_df[['isin', 'industry']],
            on='isin',
            how='left'
        )
        
        latest = latest[latest['industry'] != 'Not Available']
        latest = latest[latest['ma_200'].notna()]
        
        # Group by industry (vectorized)
        industry_trends = latest.groupby('industry').agg(
            total_stocks=('isin', 'count'),
            stocks_above_ma=('above_ma', 'sum')
        ).reset_index()
        
        industry_trends['pct_above_ma'] = (
            industry_trends['stocks_above_ma'] / industry_trends['total_stocks'] * 100
        )
        
        self._trend_metrics_cache[date] = industry_trends
        return industry_trends
    
    def select_industries(self, date, lookback_quarters, method='pure'):
        """
        Select bottom 10 and top 10 industries
        
        Args:
            date: Selection date
            lookback_quarters: 1, 2, 4, 8, or 12
            method: 'pure', 'filtered' (50%), or 'filtered_30' (30%)
        """
        # Get shareholding metrics
        sh_metrics = self.calculate_industry_shareholding_metrics(date, lookback_quarters)
        
        if len(sh_metrics) < 20:
            return None
        
        if method == 'pure':
            # Rank all industries
            sh_metrics = sh_metrics.sort_values('pct_decreasing', ascending=False)
            bottom_10 = sh_metrics.head(10)['industry'].tolist()
            top_10 = sh_metrics.tail(10)['industry'].tolist()
            
        elif method in ['filtered', 'filtered_30']:
            # Apply trend filter
            trend_metrics = self.calculate_industry_trend_metrics(date)
            
            if len(trend_metrics) == 0:
                return None
            
            # Set threshold based on method
            if method == 'filtered_30':
                threshold = trend_metrics['pct_above_ma'].quantile(0.70)  # Top 30%
            else:
                threshold = trend_metrics['pct_above_ma'].quantile(0.50)  # Top 50%
            
            trending = trend_metrics[
                trend_metrics['pct_above_ma'] >= threshold
            ]['industry'].tolist()
            
            # Filter shareholding to trending industries
            sh_filtered = sh_metrics[sh_metrics['industry'].isin(trending)]
            
            if len(sh_filtered) < 20:
                return None
            
            sh_filtered = sh_filtered.sort_values('pct_decreasing', ascending=False)
            bottom_10 = sh_filtered.head(10)['industry'].tolist()
            top_10 = sh_filtered.tail(10)['industry'].tolist()
        
        return {
            'bottom_10': bottom_10,
            'top_10': top_10
        }
    
    def get_industry_return(self, industry, start_date, end_date):
        """Get industry benchmark return between two dates"""
        if industry not in self.industry_returns:
            return np.nan
        
        ind_df = self.industry_returns[industry]
        
        try:
            # Get closest prices
            start_prices = ind_df[ind_df['date'] <= start_date]
            if len(start_prices) == 0:
                return np.nan
            start_price = start_prices.iloc[-1]['close']
            
            end_prices = ind_df[ind_df['date'] <= end_date]
            if len(end_prices) == 0:
                return np.nan
            end_price = end_prices.iloc[-1]['close']
            
            return ((end_price / start_price) - 1) * 100
        except:
            return np.nan
    
    def calculate_portfolio_return(self, industries, start_date, end_date):
        """Calculate equal-weighted portfolio return"""
        returns = []
        
        for industry in industries:
            ret = self.get_industry_return(industry, start_date, end_date)
            if not np.isnan(ret):
                returns.append(ret)
        
        if len(returns) == 0:
            return np.nan
        
        return np.mean(returns)
    
    def run_validation(self):
        """Run complete validation analysis"""
        
        print("\n" + "="*100)
        print("STARTING VALIDATION")
        print("="*100)
        
        # Parameters
        lookback_periods = [1, 2, 4, 8, 12]  # quarters
        holding_periods = [90, 180, 365]  # days
        methods = ['pure', 'filtered', 'filtered_30']
        
        # Selection dates (quarterly)
        selection_dates = pd.date_range('2019-02-15', '2024-11-15', freq='QS-FEB')
        
        print(f"\nParameters:")
        print(f"  Lookback periods: {lookback_periods} quarters")
        print(f"  Holding periods: {holding_periods} days")
        print(f"  Methods: Pure Contrarian, Trend-Filtered (50%), Trend-Filtered (30%)")
        print(f"  Selection dates: {len(selection_dates)} (from {selection_dates[0].date()} to {selection_dates[-1].date()})")
        
        all_results = []
        
        total_combinations = len(lookback_periods) * len(selection_dates) * len(methods)
        current = 0
        
        for lookback_q in lookback_periods:
            print(f"\n{'='*100}")
            print(f"Processing Lookback: {lookback_q}Q ({lookback_q*3} months)")
            print(f"{'='*100}")
            
            for date in selection_dates:
                current += len(methods)
                print(f"  [{current}/{total_combinations}] {date.date()}: ", end='')
                
                for method in methods:
                    # Select industries
                    selection = self.select_industries(date, lookback_q, method)
                    
                    if selection is None:
                        print(f"⚠️ ", end='')
                        continue
                    
                    # Calculate forward returns for each holding period
                    for holding_days in holding_periods:
                        end_date = date + pd.Timedelta(days=holding_days)
                        
                        # Bottom 10 return
                        bottom_return = self.calculate_portfolio_return(
                            selection['bottom_10'], date, end_date
                        )
                        
                        # Top 10 return
                        top_return = self.calculate_portfolio_return(
                            selection['top_10'], date, end_date
                        )
                        
                        if np.isnan(bottom_return) or np.isnan(top_return):
                            continue
                        
                        all_results.append({
                            'selection_date': date,
                            'lookback_quarters': lookback_q,
                            'holding_days': holding_days,
                            'method': method,
                            'bottom_10_return': bottom_return,
                            'top_10_return': top_return,
                            'spread': bottom_return - top_return,
                            'bottom_10_list': ','.join(selection['bottom_10']),
                            'top_10_list': ','.join(selection['top_10'])
                        })
                    
                    print("✅ ", end='')
                
                print()
        
        results_df = pd.DataFrame(all_results)
        
        # Save detailed results
        output_path = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_df.to_csv(
            output_path / f'industry_validation_detailed_{timestamp}.csv',
            index=False
        )
        print(f"\n✅ Detailed results saved: industry_validation_detailed_{timestamp}.csv")
        
        # Generate summary
        self.generate_summary(results_df, output_path, timestamp)
        
        return results_df
    
    def generate_summary(self, results_df, output_path, timestamp):
        """Generate summary statistics"""
        
        print("\n" + "="*100)
        print("GENERATING SUMMARY STATISTICS")
        print("="*100)
        
        summary_rows = []
        
        for lookback in sorted(results_df['lookback_quarters'].unique()):
            for holding in sorted(results_df['holding_days'].unique()):
                for method in results_df['method'].unique():
                    for group in ['bottom_10', 'top_10']:
                        
                        subset = results_df[
                            (results_df['lookback_quarters'] == lookback) &
                            (results_df['holding_days'] == holding) &
                            (results_df['method'] == method)
                        ]
                        
                        if len(subset) == 0:
                            continue
                        
                        returns = subset[f'{group}_return']
                        
                        # Label the method
                        if method == 'pure':
                            method_label = 'Pure Contrarian'
                        elif method == 'filtered':
                            method_label = 'Trend Filtered (50%)'
                        else:  # filtered_30
                            method_label = 'Trend Filtered (30%)'
                        
                        summary_rows.append({
                            'lookback_quarters': lookback,
                            'lookback_months': lookback * 3,
                            'holding_days': holding,
                            'method': method_label,
                            'group': group.replace('_', ' ').title(),
                            'avg_return': returns.mean(),
                            'median_return': returns.median(),
                            'std_return': returns.std(),
                            'win_rate': (returns > 0).mean() * 100,
                            'sharpe': returns.mean() / returns.std() if returns.std() > 0 else 0,
                            'best_return': returns.max(),
                            'worst_return': returns.min(),
                            'count': len(returns)
                        })
        
        summary_df = pd.DataFrame(summary_rows)
        
        # Sort by performance
        summary_df = summary_df.sort_values(
            ['lookback_quarters', 'holding_days', 'method', 'group']
        )
        
        # Save summary
        summary_df.to_csv(
            output_path / f'industry_validation_summary_{timestamp}.csv',
            index=False
        )
        
        print(f"✅ Summary saved: industry_validation_summary_{timestamp}.csv")
        
        # Display top performers
        print("\n" + "="*100)
        print("TOP 15 COMBINATIONS BY AVERAGE RETURN")
        print("="*100)
        
        top_15 = summary_df.nlargest(15, 'avg_return')
        print(top_15[['lookback_quarters', 'holding_days', 'method', 'group', 
                      'avg_return', 'win_rate', 'sharpe', 'count']].to_string(index=False))
        
        # Display spread analysis
        print("\n" + "="*100)
        print("SPREAD ANALYSIS (Bottom 10 - Top 10)")
        print("="*100)
        
        spread_summary = results_df.groupby(
            ['lookback_quarters', 'holding_days', 'method']
        )['spread'].agg([
            ('Avg Spread', 'mean'),
            ('Median Spread', 'median'),
            ('Std Dev', 'std'),
            ('Win Rate %', lambda x: (x > 0).mean() * 100),
            ('Count', 'count')
        ]).round(2)
        
        print(spread_summary.to_string())
        
        spread_summary.to_csv(
            output_path / f'industry_validation_spread_{timestamp}.csv'
        )
        
        print(f"\n✅ Spread analysis saved: industry_validation_spread_{timestamp}.csv")
        
        # Best combination analysis
        print("\n" + "="*100)
        print("BEST LOOKBACK & HOLDING COMBINATIONS")
        print("="*100)
        
        best_combos = summary_df[
            summary_df['group'] == 'Bottom 10'
        ].nlargest(10, 'avg_return')
        
        print("\nTop 10 Bottom 10 Industry Selections:")
        print(best_combos[['lookback_quarters', 'holding_days', 'method', 
                          'avg_return', 'win_rate', 'sharpe']].to_string(index=False))
        
        return summary_df


def main():
    """Run the validation"""
    validator = IndustrySelectionValidation()
    results = validator.run_validation()
    
    print("\n" + "="*100)
    print("✅ VALIDATION COMPLETE")
    print("="*100)
    print(f"Total results generated: {len(results):,}")
    print(f"\nFiles saved in: analysis/outputs/reports/")
    print(f"  - industry_validation_detailed_*.csv")
    print(f"  - industry_validation_summary_*.csv")
    print(f"  - industry_validation_spread_*.csv")


if __name__ == "__main__":
    main()
