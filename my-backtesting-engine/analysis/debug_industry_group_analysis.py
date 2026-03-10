"""Debug script to test industry group analysis logic"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path('.')
DATABASE_DIR = BASE_DIR / 'database'

# Load shareholding patterns
print("Loading shareholding patterns...")
shp_df = pd.read_csv(DATABASE_DIR / 'shareholding_patterns.csv')

def parse_quarter_to_date(quarter_str):
    try:
        if '-' in str(quarter_str):
            parts = str(quarter_str).split('-')
            if len(parts) == 2:
                month_str, year_str = parts
                month_map = {
                    'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12,
                    'March': 3, 'June': 6, 'September': 9, 'December': 12
                }
                month = month_map.get(month_str, 12)
                year = int(year_str)
                from calendar import monthrange
                day = monthrange(year, month)[1]
                return pd.Timestamp(year=year, month=month, day=day)
        return pd.NaT
    except:
        return pd.NaT

shp_df['date'] = shp_df['quarter'].apply(parse_quarter_to_date)

# Load industry info
print("Loading industry info...")
industry_df = pd.read_csv(DATABASE_DIR / 'industry_info.csv')
industry_df = industry_df[industry_df['industry_group'] != 'Other']
isin_to_industry = dict(zip(industry_df['isin'], industry_df['industry_group']))

# Test specific rebalance date
rebalance_date = pd.Timestamp('2020-02-15')
lookback_quarters = 1
print(f"\nTesting rebalance date: {rebalance_date}")
print(f"Lookback: {lookback_quarters} quarters")

# Get shareholding data at rebalance date
current_shp = shp_df[shp_df['date'] == rebalance_date].copy()
print(f"  Shareholding records at {rebalance_date}: {len(current_shp)}")

# Get lookback date
lookback_date = rebalance_date - pd.DateOffset(months=lookback_quarters * 3)
past_shp = shp_df[shp_df['date'] == lookback_date].copy()
print(f"  Shareholding records at {lookback_date}: {len(past_shp)}")

if len(current_shp) > 0 and len(past_shp) > 0:
    # Merge
    merged = current_shp.merge(
        past_shp[['isin', 'total_shareholders']],
        on='isin',
        how='inner',
        suffixes=('_current', '_past')
    )
    print(f"  Merged records: {len(merged)}")
    
    # Add industry group
    merged['industry_group'] = merged['isin'].map(isin_to_industry)
    merged = merged.dropna(subset=['industry_group'])
    print(f"  After industry mapping: {len(merged)}")
    
    # Calculate change
    merged['shareholder_change'] = (
        merged['total_shareholders_current'] - merged['total_shareholders_past']
    )
    merged['is_increasing'] = merged['shareholder_change'] > 0
    
    # Group by industry_group
    industry_metrics = {}
    for industry_group in merged['industry_group'].unique():
        group_data = merged[merged['industry_group'] == industry_group]
        num_stocks = len(group_data)
        
        if num_stocks < 5:  # min_stocks_per_group
            continue
        
        num_increasing = group_data['is_increasing'].sum()
        pct_increasing = (num_increasing / num_stocks) * 100
        
        industry_metrics[industry_group] = {
            'num_stocks': num_stocks,
            'pct_increasing': pct_increasing
        }
    
    print(f"\n  Industry groups with >= 5 stocks: {len(industry_metrics)}")
    
    # Sort and select top/bottom 5
    sorted_groups = sorted(
        industry_metrics.items(),
        key=lambda x: x[1]['pct_increasing'],
        reverse=True
    )
    
    print(f"\n  Top 5 groups (highest % increasing):")
    for group, metrics in sorted_groups[:5]:
        print(f"    {group}: {metrics['pct_increasing']:.1f}% increasing ({metrics['num_stocks']} stocks)")
    
    print(f"\n  Bottom 5 groups (lowest % increasing):")
    for group, metrics in sorted_groups[-5:]:
        print(f"    {group}: {metrics['pct_increasing']:.1f}% increasing ({metrics['num_stocks']} stocks)")
    
    # Now check benchmark availability
    print("\n  Checking benchmark data availability...")
    benchmark_base = Path('analysis/outputs/benchmarks/industry_groups')
    
    top_groups = [group for group, _ in sorted_groups[:5]]
    for group in top_groups[:3]:  # Check first 3
        group_dir_name = group.replace(' ', '_')
        timeseries_file = benchmark_base / group_dir_name / 'timeseries.csv'
        if timeseries_file.exists():
            df = pd.read_csv(timeseries_file)
            df['date'] = pd.to_datetime(df['date'])
            print(f"    {group}: {len(df)} benchmark records")
            print(f"      Date range: {df['date'].min()} to {df['date'].max()}")
            
            # Check if we have data near rebalance_date
            nearby_dates = df[
                (df['date'] >= rebalance_date - pd.Timedelta(days=30)) &
                (df['date'] <= rebalance_date + pd.Timedelta(days=30))
            ]
            print(f"      Dates near {rebalance_date}: {len(nearby_dates)}")
            if len(nearby_dates) > 0:
                print(f"        {nearby_dates['date'].tolist()}")
        else:
            print(f"    {group}: NO TIMESERIES FILE")
else:
    print("  No data to merge")
