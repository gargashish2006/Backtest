#!/usr/bin/env python
"""
Market Analysis: Sentiment (Shareholder Change) vs Trend Breadh (200 SMA)
Compares these metrics against the Top 1000 Benchmark.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def parse_quarter_to_date(quarter_str):
    try:
        parts = str(quarter_str).split('-')
        month_map = {'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12, 'March': 3, 'June': 6, 'September': 9, 'December': 12}
        month = month_map.get(parts[0], 12)
        year = int(parts[1])
        from calendar import monthrange
        return pd.Timestamp(year=year, month=month, day=monthrange(year, month)[1])
    except: return pd.NaT

def main():
    base_path = Path('.')
    db_path = base_path / 'database'
    output_path = base_path / 'analysis/outputs'
    output_path.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    price_df = pd.read_parquet(db_path / 'price_data.parquet')
    shp_df = pd.read_parquet(db_path / 'shareholding_patterns.parquet')
    benchmark_path = base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
    bench_df = pd.read_csv(benchmark_path)
    shares_df = pd.read_csv(db_path / 'outstanding_shares.csv') if (db_path / 'outstanding_shares.csv').exists() else None
    
    print("Preprocessing prices...")
    price_df['date'] = pd.to_datetime(price_df['date'])
    price_df = price_df.sort_values(['isin', 'date'])
    price_df['ma_200'] = price_df.groupby('isin')['close'].transform(lambda x: x.rolling(200, min_periods=150).mean())
    price_df['above_ma'] = (price_df['close'] > price_df['ma_200']).astype(int)
    
    print("Preprocessing shareholders...")
    shp_df['quarter_date'] = shp_df['quarter'].apply(parse_quarter_to_date)
    shp_df = shp_df.sort_values(['isin', 'quarter_date'])
    shp_df['prev_sh'] = shp_df.groupby('isin')['total_shareholders'].shift(4)
    shp_df['sh_increase'] = ((shp_df['total_shareholders'] - shp_df['prev_sh']) > 0).astype(int)
    
    # Map ISIN to latest shares
    if shares_df is not None:
        shares_map = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
    else:
        shares_map = dict(zip(shp_df.groupby('isin').last().index, shp_df.groupby('isin').last()['total_outstanding_shares']))

    # Generate Monthly Dates
    analysis_dates = pd.date_range('2017-01-01', '2025-11-01', freq='ME')
    results = []

    print("Calculating metrics per month...")
    for d in analysis_dates:
        # 1. Trend Metric: % Above MA
        # Get latest price before or on date
        p_slice = price_df[price_df['date'] <= d].groupby('isin').last().reset_index()
        p_slice = p_slice[p_slice['date'] > d - pd.Timedelta(days=30)] # Recency check
        
        if p_slice.empty: continue
        
        # 2. Sentiment Metric: % Sh Increase
        # Get latest shareholder data before or on date
        s_slice = shp_df[shp_df['quarter_date'] <= d].groupby('isin').last().reset_index()
        s_slice = s_slice[s_slice['quarter_date'] > d - pd.Timedelta(days=120)] # Recency check
        
        # 3. Benchmark universe (Top 1000 by MCAP on this date)
        p_slice['mcap'] = p_slice['close'] * p_slice['isin'].map(shares_map)
        p_slice = p_slice.dropna(subset=['mcap']).sort_values('mcap', ascending=False)
        top_1000 = p_slice.head(1000)
        
        # Filter metrics for Top 1000 universe
        merged = top_1000.merge(s_slice[['isin', 'sh_increase']], on='isin', how='left')
        
        pct_above_ma = merged['above_ma'].mean() * 100
        pct_sh_increase = merged['sh_increase'].mean() * 100 # Note: some might be NaN if no SHP data
        
        results.append({
            'date': d,
            'pct_above_ma': pct_above_ma,
            'pct_sh_increase': pct_sh_increase
        })

    metrics_df = pd.DataFrame(results)
    
    # Merge with benchmark price
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    metrics_df = metrics_df.merge(bench_df[['date', 'index_value']], on='date', how='left')
    
    # Forward fill benchmark values (re-sampling might skip weekend-only benchmark dates)
    metrics_df['index_value'] = metrics_df['index_value'].ffill()
    
    # Plotting
    print("Generating plot...")
    fig, ax1 = plt.subplots(figsize=(15, 8))

    # Ax1: Percentages (Sentiment and Breadth)
    ax1.plot(metrics_df['date'], metrics_df['pct_sh_increase'], label='% Stocks w/ 4Q Shareholder Increase', color='#ff7f0e', linewidth=2)
    ax1.plot(metrics_df['date'], metrics_df['pct_above_ma'], label='% Stocks Above 200 SMA', color='#1f77b4', linewidth=2)
    
    ax1.axhline(50, color='gray', linestyle='--', alpha=0.5)
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Percentage (%)', fontsize=12)
    ax1.set_ylim(0, 100)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=10)

    # Ax2: Benchmark Price (Log Scale often better for price)
    ax2 = ax1.twinx()
    ax2.plot(metrics_df['date'], metrics_df['index_value'], label='Top 1000 Benchmark (RHS)', color='black', alpha=0.3, linewidth=2, linestyle=':')
    ax2.set_ylabel('Benchmark Index Value', color='black', fontsize=12)
    
    plt.title('Market Dynamics: Shareholder Sentiment vs. Trend Breadth (Top 1000 Stocks)', fontsize=16, pad=20)
    
    # Save the plot
    plot_file = output_path / 'sentiment_vs_trend_analysis.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to: {plot_file}")
    
    # Save data
    metrics_df.to_csv(output_path / 'sentiment_vs_trend_metrics.csv', index=False)
    print(f"✅ Data saved to: {output_path / 'sentiment_vs_trend_metrics.csv'}")

if __name__ == "__main__":
    main()
