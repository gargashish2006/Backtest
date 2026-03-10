#!/usr/bin/env python
"""
Analyze top 20% industries by contrarian signal from latest data point
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    # Load data
    base_path = Path(__file__).parent
    database_path = base_path / 'database'

    print('Loading data...')
    shp_df = pd.read_parquet(database_path / 'shareholding_patterns.parquet')
    industry_df = pd.read_parquet(database_path / 'industry_info.parquet')
    price_df = pd.read_parquet(database_path / 'price_data.parquet')

    # Parse quarter dates
    def parse_quarter_to_date(quarter_str):
        month_map = {'Mar': '03', 'Jun': '06', 'Sep': '09', 'Dec': '12'}
        quarter, year = quarter_str.split('-')
        return f'{year}-{month_map[quarter]}-01'

    shp_df['quarter_date'] = shp_df['quarter'].apply(parse_quarter_to_date)
    shp_df['quarter_date'] = pd.to_datetime(shp_df['quarter_date'])

    # Get latest quarter - USE DEC-2025 instead of latest
    latest_quarter = pd.to_datetime('2025-12-01')
    print(f'Using quarter: {latest_quarter.strftime("%Y-%m-%d")} (Dec-2025)')

    # Get 4 quarters for lookback - USER WANTS: Dec-2025 vs Dec-2024 comparison
    quarters_needed = [pd.to_datetime('2024-12-01'), pd.to_datetime('2025-12-01')]

    print(f'Using quarters for comparison: {[q.strftime("%Y-%m-%d") for q in quarters_needed]} (Dec-2025 vs Dec-2024)')

    # Filter data for these quarters
    shp_filtered = shp_df[shp_df['quarter_date'].isin(quarters_needed)].copy()

    # Filter data for these quarters
    shp_filtered = shp_df[shp_df['quarter_date'].isin(quarters_needed)].copy()

    # Merge with industry info
    shp_with_industry = pd.merge(shp_filtered, industry_df[['isin', 'industry']], on='isin', how='left')

    # Calculate shareholding changes for each stock over 2 quarters (Dec-2025 vs Dec-2024)
    print('Calculating shareholding changes (Dec-2025 vs Dec-2024)...')
    shareholding_changes = []

    for isin in shp_with_industry['isin'].unique():
        stock_data = shp_with_industry[shp_with_industry['isin'] == isin].sort_values('quarter_date')
        if len(stock_data) >= 2:
            # Compare Dec-2025 vs Dec-2024
            dec2025_data = stock_data[stock_data['quarter_date'] == pd.to_datetime('2025-12-01')]
            dec2024_data = stock_data[stock_data['quarter_date'] == pd.to_datetime('2024-12-01')]

            if len(dec2025_data) > 0 and len(dec2024_data) > 0:
                latest_shp = dec2025_data.iloc[0]['total_shareholders']
                earliest_shp = dec2024_data.iloc[0]['total_shareholders']
                change_pct = (latest_shp - earliest_shp) / earliest_shp if earliest_shp > 0 else 0
                industry = stock_data['industry'].iloc[0]
                shareholding_changes.append({
                    'isin': isin,
                    'industry': industry,
                    'change_pct': change_pct
                })

    changes_df = pd.DataFrame(shareholding_changes)
    print(f'Processed {len(changes_df)} stocks with complete 2Q data (Dec-2025 vs Dec-2024)')

    # Calculate contrarian signal per industry (% of stocks with decreasing shareholders)
    print('Calculating contrarian signals per industry...')
    industry_signals = []

    for industry in changes_df['industry'].unique():
        industry_stocks = changes_df[changes_df['industry'] == industry]
        decreasing_pct = (industry_stocks['change_pct'] < 0).mean()
        industry_signals.append({
            'industry': industry,
            'contrarian_signal': decreasing_pct,
            'total_stocks': len(industry_stocks)
        })

    signals_df = pd.DataFrame(industry_signals)
    print(f'Found {len(signals_df)} industries with shareholding data')

    # Get top 20% industries by contrarian signal
    top_20pct_count = int(len(signals_df) * 0.2)
    top_industries = signals_df.nlargest(top_20pct_count, 'contrarian_signal')

    print(f'\nTop 20% industries by contrarian signal ({top_20pct_count} out of {len(signals_df)}):')
    print('=' * 80)
    for idx, row in top_industries.iterrows():
        print(f"{row['industry']:<30} | Contrarian: {row['contrarian_signal']:.1%} | Stocks: {row['total_stocks']}")

    # Now calculate trend strength for these top industries
    print('\nCalculating trend strength (distance from 52-week high for median stock)...')

    # Use price data as of last available date (2026-01-28)
    last_price_date = pd.to_datetime('2026-01-28')
    print(f'Using price data as of: {last_price_date.strftime("%Y-%m-%d")}')

    # Filter price data to last date
    latest_prices = price_df[price_df['date'] == last_price_date].copy()

    # Calculate 52-week highs (rolling max over past 252 trading days)
    price_df_filtered = price_df[price_df['date'] <= last_price_date].copy()
    price_df_sorted = price_df_filtered.sort_values(['isin', 'date'])

    # Calculate 52-week high for each stock
    price_df_sorted['52w_high'] = price_df_sorted.groupby('isin')['high'].transform(lambda x: x.rolling(252).max())

    # Get latest 52-week high values for the last price date
    latest_52w = price_df_sorted[price_df_sorted['date'] == last_price_date][['isin', 'close', '52w_high']].copy()

    # Merge with industry info
    latest_52w_with_industry = pd.merge(latest_52w, industry_df[['isin', 'industry']], on='isin', how='left')

    # Calculate trend strength for top industries based on median stock's distance from 52W high
    trend_analysis = []

    for industry in top_industries['industry']:
        industry_stocks = latest_52w_with_industry[latest_52w_with_industry['industry'] == industry]
        if len(industry_stocks) > 0:
            # Calculate distance from 52W high for each stock
            industry_stocks = industry_stocks.copy()
            industry_stocks['distance_from_52w'] = (industry_stocks['52w_high'] - industry_stocks['close']) / industry_stocks['52w_high']

            # Find median stock's distance (50th percentile)
            median_distance = industry_stocks['distance_from_52w'].median()

            # Trend strength = 1 - median_distance (higher = closer to 52W high = stronger trend)
            trend_strength = 1 - median_distance

            # Count stocks within 10% of 52W high (traditional definition of "near 52W high")
            near_52w_count = (industry_stocks['distance_from_52w'] <= 0.10).sum()

            # Get one example stock from this industry
            example_stock = industry_stocks.iloc[0]  # Take first stock as example
            example_isin = example_stock['isin']
            example_name = shp_df[shp_df['isin'] == example_isin]['company_name'].iloc[0] if len(shp_df[shp_df['isin'] == example_isin]) > 0 else 'Unknown'

            trend_analysis.append({
                'industry': industry,
                'trend_strength': trend_strength,
                'near_52w_high': near_52w_count,
                'total_stocks': len(industry_stocks),
                'median_distance_from_52w': median_distance,
                'example_stock': f"{example_name} ({example_isin})"
            })

    trend_df = pd.DataFrame(trend_analysis)

    # Merge with contrarian signals and sort by trend strength
    final_results = pd.merge(top_industries, trend_df, on='industry')
    final_results = final_results.sort_values('trend_strength', ascending=False)

    print('\nTop 20% industries ranked by trend strength (best first):')
    print('=' * 120)
    print('Rank | Industry | Contrarian | Trend | Near 52W High | Median Dist | Example Stock')
    print('-' * 120)

    for rank, (_, row) in enumerate(final_results.iterrows(), 1):
        total_stocks = row.get('total_stocks_y', row.get('total_stocks_x', row.get('total_stocks', 'N/A')))
        example_stock = row.get('example_stock', 'N/A')
        median_dist = row.get('median_distance_from_52w', 'N/A')
        near_52w = row.get('near_52w_high', 'N/A')
        print(f"{rank:2d}   | {row['industry']:<30} | {row['contrarian_signal']:.1%} | {row['trend_strength']:.1%} | {near_52w}/{total_stocks} | {median_dist:.1%} | {example_stock}")

if __name__ == "__main__":
    main()