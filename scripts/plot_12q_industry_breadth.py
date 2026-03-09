import sys
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from data.data_handler import DataHandler

def plot_historical_breadth():
    print("Loading data...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # We need quarterly dates to evaluate
    all_dates = dh.get_all_dates()
    eval_dates = []
    # Data realistically starts becoming useful after a 3-year lookback buffer.
    # We will compute from 2018 onwards to see whatever is available.
    for y in range(2018, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            past_dates = [dt for dt in all_dates if dt <= d]
            if past_dates:
                eval_dates.append(max(past_dates))
                
    eval_dates = sorted(list(set(eval_dates)))
    
    results = []
    
    print("Calculating historical 12Q breadth...")
    for d in eval_dates:
        sh_trend = dh.get_shareholder_trend(d, lookback_quarters=12)
        if sh_trend.empty:
            continue
            
        sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
        sh_trend = sh_trend.dropna(subset=['industry'])
        
        if sh_trend.empty:
            continue
            
        # Filter for top 1000 at this date for relevant breadth
        universe = dh.get_universe(d, size=1000)
        if universe.empty:
            continue
            
        valid_isins = set(universe['isin'])
        sh_trend_top1000 = sh_trend[sh_trend['isin'].isin(valid_isins)]
        
        ind_stats = sh_trend_top1000.groupby('industry').agg(
            total_stocks=('decreased', 'count'),
            decreased_stocks=('decreased', 'sum')
        ).reset_index()
        
        # We only consider industries with at least 3 stocks in top 1000 to avoid noise
        ind_stats = ind_stats[ind_stats['total_stocks'] >= 3].copy()
        
        if ind_stats.empty:
            continue
            
        ind_stats['breadth_pct'] = ind_stats['decreased_stocks'] / ind_stats['total_stocks']
        
        industries_above_50 = len(ind_stats[ind_stats['breadth_pct'] > 0.50])
        total_industries = len(ind_stats)
        
        pct_above_50 = (industries_above_50 / total_industries) * 100 if total_industries > 0 else 0
        
        # Get benchmark
        b_prices = dh.top_1000_bench
        bench_val = b_prices[b_prices['date'] <= d]['index_value'].iloc[-1] if not b_prices[b_prices['date'] <= d].empty else np.nan
        
        results.append({
            'date': d,
            'pct_industries_above_50': pct_above_50,
            'benchmark': bench_val
        })
        
    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        print("No results calculated.")
        return
        
    df_results = df_results.dropna()
    
    print("Plotting...")
    fig, ax1 = plt.subplots(figsize=(14, 8))

    color = 'tab:red'
    ax1.set_xlabel('Date')
    ax1.set_ylabel('% of Industries with >50% 12Q Breadth', color=color)
    ax1.plot(df_results['date'], df_results['pct_industries_above_50'], color=color, linewidth=2, label='% Industries > 50% Breadth')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Add horizontal lines for reference
    ax1.axhline(50, color='gray', linestyle='--', alpha=0.5)

    ax2 = ax1.twinx()  
    color = 'tab:blue'
    ax2.set_ylabel('Top 1000 Benchmark', color=color)  
    ax2.plot(df_results['date'], df_results['benchmark'], color=color, linewidth=2, alpha=0.8, label='Top 1000 Benchmark')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_yscale('log') # Log scale for benchmark is usually better
    
    fig.tight_layout()  
    plt.title('Percentage of Industries with >50% Institutional Accumulation (12Q Breadth) vs Benchmark')
    
    save_path = repo_root / "industry_12q_breadth_vs_benchmark.png"
    plt.savefig(save_path)
    print(f"Saved plot to {save_path}")

if __name__ == "__main__":
    plot_historical_breadth()
