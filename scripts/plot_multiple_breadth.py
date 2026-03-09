import sys
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from data.data_handler import DataHandler

def plot_historical_breadth_multiple():
    print("Loading data...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    all_dates = dh.get_all_dates()
    eval_dates = []
    for y in range(2018, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            past_dates = [dt for dt in all_dates if dt <= d]
            if past_dates:
                eval_dates.append(max(past_dates))
                
    eval_dates = sorted(list(set(eval_dates)))
    
    results = []
    
    print("Calculating historical 12Q, 8Q, and 4Q breadth...")
    for d in eval_dates:
        universe = dh.get_universe(d, size=1000)
        if universe.empty:
            continue
        valid_isins = set(universe['isin'])
        
        def get_pct_above_50(lookback):
            sh_trend = dh.get_shareholder_trend(d, lookback_quarters=lookback)
            if sh_trend.empty: return np.nan
            sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
            sh_trend = sh_trend.dropna(subset=['industry'])
            if sh_trend.empty: return np.nan
            
            sh_trend_top1000 = sh_trend[sh_trend['isin'].isin(valid_isins)]
            ind_stats = sh_trend_top1000.groupby('industry').agg(
                total_stocks=('decreased', 'count'),
                decreased_stocks=('decreased', 'sum')
            ).reset_index()
            
            ind_stats = ind_stats[ind_stats['total_stocks'] >= 3].copy()
            if ind_stats.empty: return np.nan
            
            ind_stats['breadth_pct'] = ind_stats['decreased_stocks'] / ind_stats['total_stocks']
            industries_above_50 = len(ind_stats[ind_stats['breadth_pct'] > 0.50])
            total_industries = len(ind_stats)
            return (industries_above_50 / total_industries) * 100 if total_industries > 0 else np.nan

        pct_12q = get_pct_above_50(12)
        pct_8q = get_pct_above_50(8)
        pct_4q = get_pct_above_50(4)
        
        # Calculate 200DMA & 50DMA Breadth
        past_1_yr = sorted([dt for dt in all_dates if dt <= d])[-200:]
        if len(past_1_yr) > 0:
            prices_200d = dh.price_df[dh.price_df['date'].isin(past_1_yr)]
            prices_200d = prices_200d[prices_200d['isin'].isin(valid_isins)]
            
            # Get latest close and moving averages
            latest_prices = prices_200d[prices_200d['date'] == past_1_yr[-1]].set_index('isin')['close']
            ma200 = prices_200d.groupby('isin')['close'].mean()
            
            past_50d_dates = past_1_yr[-50:]
            prices_50d = prices_200d[prices_200d['date'].isin(past_50d_dates)]
            ma50 = prices_50d.groupby('isin')['close'].mean()
            
            # Align and compare
            compare_df = pd.DataFrame({'close': latest_prices, 'ma200': ma200, 'ma50': ma50}).dropna()
            if not compare_df.empty:
                above_200dma = (compare_df['close'] > compare_df['ma200']).sum()
                pct_above_200dma = (above_200dma / len(compare_df)) * 100
                
                above_50dma = (compare_df['close'] > compare_df['ma50']).sum()
                pct_above_50dma = (above_50dma / len(compare_df)) * 100
            else:
                pct_above_200dma = np.nan
                pct_above_50dma = np.nan
        else:
            pct_above_200dma = np.nan
            pct_above_50dma = np.nan
        
        b_prices = dh.top_1000_bench
        bench_val = b_prices[b_prices['date'] <= d]['index_value'].iloc[-1] if not b_prices[b_prices['date'] <= d].empty else np.nan
        
        results.append({
            'date': d,
            'pct_12q': pct_12q,
            'pct_8q': pct_8q,
            'pct_4q': pct_4q,
            'pct_above_200dma': pct_above_200dma,
            'pct_above_50dma': pct_above_50dma,
            'benchmark': bench_val
        })
        
    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        print("No results calculated.")
        return
        
    df_results['benchmark'] = df_results['benchmark'].ffill()
    
    print("Plotting...")
    fig, ax1 = plt.subplots(figsize=(14, 8))

    ax1.set_xlabel('Date')
    ax1.set_ylabel('% of Industries >50% Breadth / % Stocks > MAs')
    
    # Plot Shareholder Breadths
    ax1.plot(df_results['date'], df_results['pct_12q'], color='tab:red', linewidth=2, label='12Q Breadth > 50%')
    ax1.plot(df_results['date'], df_results['pct_8q'], color='tab:orange', linewidth=2, linestyle='--', label='8Q Breadth > 50%')
    ax1.plot(df_results['date'], df_results['pct_4q'], color='tab:green', linewidth=2, linestyle='-.', label='4Q Breadth > 50%')
    
    # Plot DMA Breadth
    ax1.plot(df_results['date'], df_results['pct_above_200dma'], color='m', linewidth=2, linestyle=':', label='% Stocks > 200DMA')
    ax1.plot(df_results['date'], df_results['pct_above_50dma'], color='c', linewidth=2, linestyle=':', label='% Stocks > 50DMA')
    
    ax1.tick_params(axis='y')
    ax1.axhline(50, color='gray', linestyle='-', alpha=0.3)
    ax1.legend(loc='upper left')

    ax2 = ax1.twinx()  
    color = 'tab:blue'
    ax2.set_ylabel('Top 1000 Benchmark', color=color)  
    ax2.plot(df_results['date'], df_results['benchmark'], color=color, linewidth=2, alpha=0.6, label='Top 1000 Benchmark')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_yscale('log')
    ax2.legend(loc='lower right')
    
    fig.tight_layout()  
    plt.title('Percentage of Industries with >50% Breadth (12Q, 8Q, 4Q) vs Benchmark')
    
    save_path = repo_root / "industry_breadth_multiple_vs_benchmark.png"
    plt.savefig(save_path)
    print(f"Saved plot to {save_path}")

if __name__ == "__main__":
    plot_historical_breadth_multiple()
