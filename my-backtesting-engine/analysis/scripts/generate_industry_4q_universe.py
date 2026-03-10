#!/usr/bin/env python
"""
Generate stock universe for 'industry_4q_top20pct_10ind_3stocks' strategy.
Logic:
1. Identify industries with highest 'Contrarian Signal' (decreasing shareholders) over 4 quarters (Dec 25 vs Dec 24).
2. Select Top 20% of these industries.
3. Take the Top 10 industries from this list.
4. For each industry, select Top 3 stocks closest to their 52-week high.
5. Output ISINs to CSV.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
base_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(base_path))

def main():
    database_path = base_path / 'database'
    output_file = base_path / 'industry_4q_top20pct_10ind_3stocks.csv'

    print(f"Generating universe to: {output_file}")
    
    # Load data
    print('Loading data...')
    try:
        shp_df = pd.read_parquet(database_path / 'shareholding_patterns.parquet')
        industry_df = pd.read_parquet(database_path / 'industry_info.parquet')
        price_df = pd.read_parquet(database_path / 'price_data.parquet')
        master_df = pd.read_parquet(database_path / 'master_identifiers.parquet') # Need this for symbols?
    except Exception as e:
        print(f"Error loading parquet files (trying CSV...): {e}")
        # Fallback to CSV if parquet fails
        shp_df = pd.read_csv(database_path / 'shareholding_patterns.csv')
        industry_df = pd.read_csv(database_path / 'industry_info.csv')
        price_df = pd.read_csv(database_path / 'price_data.csv')
        master_df = pd.read_csv(database_path / 'master_identifiers.csv')

    # Parse dates
    if 'quarter_date' not in shp_df.columns:
        def parse_quarter_to_date(quarter_str):
            month_map = {'Mar': '03', 'Jun': '06', 'Sep': '09', 'Dec': '12'}
            try:
                quarter, year = quarter_str.split('-')
                return f'{year}-{month_map[quarter]}-01'
            except:
                return None
        
        shp_df['quarter_date'] = shp_df['quarter'].apply(parse_quarter_to_date)
        shp_df['quarter_date'] = pd.to_datetime(shp_df['quarter_date'])

    if 'date' in price_df.columns:
        price_df['date'] = pd.to_datetime(price_df['date'])

    # 1. Calculate Contrarian Signal (4Q Change: Dec 2025 vs Dec 2024)
    # Note: Using Dec 2025 and Dec 2024 as in analyze_top_industries.py
    
    quarters_needed = [pd.to_datetime('2024-12-01'), pd.to_datetime('2025-12-01')]
    shp_filtered = shp_df[shp_df['quarter_date'].isin(quarters_needed)].copy()
    
    # Merge industry info
    shp_with_industry = pd.merge(shp_filtered, industry_df[['isin', 'industry']], on='isin', how='left')
    shp_with_industry = shp_with_industry[shp_with_industry['industry'].notna()]

    print('Calculating shareholding changes...')
    
    # Pivot to get changes
    pivot_shp = shp_with_industry.pivot_table(
        index=['isin', 'industry'], 
        columns='quarter_date', 
        values='total_shareholders'
    ).reset_index()
    
    # Check if columns exist
    d1 = quarters_needed[0]
    d2 = quarters_needed[1]
    
    if d1 not in pivot_shp.columns or d2 not in pivot_shp.columns:
        print(f"Error: Data for {d1} or {d2} missing in pivot.")
        return

    # Calculate change
    pivot_shp['change_pct'] = (pivot_shp[d2] - pivot_shp[d1]) / pivot_shp[d1]
    pivot_shp = pivot_shp.dropna(subset=['change_pct']) # Only stocks with both quarters
    
    # 2. Industry Level Signals
    print('Calculating industry signals...')
    industry_stats = pivot_shp.groupby('industry').agg(
        total_stocks=('isin', 'count'),
        decreasing_count=('change_pct', lambda x: (x < 0).sum())
    ).reset_index()
    
    industry_stats['contrarian_signal'] = industry_stats['decreasing_count'] / industry_stats['total_stocks']
    
    # Filter small industries
    industry_stats = industry_stats[industry_stats['total_stocks'] >= 5]
    
    # Top 20% by Contrarian Signal
    top_20pct_count = int(len(industry_stats) * 0.2)
    top_20pct_industries = industry_stats.nlargest(top_20pct_count, 'contrarian_signal')
    
    print(f"Top 20% industries count: {len(top_20pct_industries)}")
    
    # 3. Select Top 10 Industries
    # We take the top 10 from the top 20% (simply the top 10 highest signal)
    top_10_industries = top_20pct_industries.head(10)
    
    print("Selected Top 10 Industries:")
    for _, row in top_10_industries.iterrows():
        print(f"  {row['industry']} ({row['contrarian_signal']:.1%})")

    # 4. Select Top 3 Stocks per Industry (Closest to 52w High)
    print('\nSelecting Top 3 Stocks per industry...')
    
    last_price_date = price_df['date'].max()
    print(f"Using price data as of: {last_price_date.date()}")
    
    # Filter last year prices for 52w high
    start_date_1y = last_price_date - pd.Timedelta(days=365)
    price_1y = price_df[price_df['date'] >= start_date_1y].copy()
    
    # Calculate 52w Highs per stock
    highs = price_1y.groupby('isin')['high'].max().reset_index()
    highs.rename(columns={'high': 'high_52w'}, inplace=True)
    
    # Get latest close
    latest_prices = price_df[price_df['date'] == last_price_date][['isin', 'close', 'symbol']].copy() # Include symbol if avail
    
    # Merge metrics
    stock_metrics = pd.merge(latest_prices, highs, on='isin')
    stock_metrics['dist_from_high'] = (stock_metrics['high_52w'] - stock_metrics['close']) / stock_metrics['high_52w']
    
    # Merge with Industry info
    stock_metrics = pd.merge(stock_metrics, industry_df[['isin', 'industry']], on='isin')
    
    # Only keep stocks from selected industries
    target_stocks = stock_metrics[stock_metrics['industry'].isin(top_10_industries['industry'])].copy()
    
    # OPTIONAL: Filter for those with Decreasing Shareholders ONLY?
    # The strategy name doesn't explicitly say "decreasing only", but "Contrarian" implies it.
    # However, "3 stocks" usually implies "Best 3". 
    # Let's prioritize stocks with Decreasing Shareholders AND close to 52w high.
    # We can join with pivot_shp to get 'change_pct'
    
    target_stocks = pd.merge(target_stocks, pivot_shp[['isin', 'change_pct']], on='isin', how='left')
    
    # Filter: Only Decreasing Shareholders (change_pct < 0)
    # This aligns with "Contrarian" logic.
    decreasing_stocks = target_stocks[target_stocks['change_pct'] < 0].copy()
    
    final_universe = []
    
    for industry in top_10_industries['industry']:
        ind_stocks = decreasing_stocks[decreasing_stocks['industry'] == industry]
        
        # If not enough decreasing stocks, fall back to all stocks in industry? 
        # Let's stick to strict contrarian first.
        
        # Sort by distance from high (ascending -> closest to high)
        ind_stocks = ind_stocks.sort_values('dist_from_high', ascending=True)
        
        # Take Top 3
        top_3 = ind_stocks.head(3)
        final_universe.extend(top_3['isin'].tolist())
        
        print(f"  {industry}: Selected {len(top_3)} stocks")
        for _, stock in top_3.iterrows():
             print(f"    - {stock['isin']} (Dist: {stock['dist_from_high']:.1%}, SH Change: {stock['change_pct']:.1%})")

    # Output CSV
    universe_df = pd.DataFrame({'isin': final_universe})
    universe_df.to_csv(output_file, index=False)
    print(f"\nSaved {len(universe_df)} stocks to {output_file}")

if __name__ == "__main__":
    main()
