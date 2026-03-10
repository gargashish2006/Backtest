import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import sys

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

from data.data_handler import DataHandler

def plot_market_breadth():
    print("Loading data...")
    # Load prices
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    
    # We want data from ~2017 onwards to match backtest lengths
    start_date = pd.Timestamp('2017-01-01')
    
    # 1. Load Nifty 500 index data
    indices_path = repo_root / "database/indices_data.parquet"
    if not indices_path.exists():
        print(f"Error: {indices_path} not found.")
        return
        
    df_idx = pd.read_parquet(indices_path)
    n500 = df_idx[df_idx['index_name'] == 'NIFTY 500'].copy()
    n500['date'] = pd.to_datetime(n500['date'])
    n500 = n500[n500['date'] >= start_date].sort_values('date')
    
    # 2. Calculate Market Breadth for top 1000 universe each day 
    print("Pivoting data...")
    # We need both close prices and market cap
    df_p = dh.price_df[dh.price_df['date'] >= (start_date - pd.Timedelta(days=400))] # buffer
    
    # Pivot to get daily close prices and market caps
    price_pivot = df_p.pivot(index='date', columns='isin', values='close').sort_index()
    mc_pivot = df_p.pivot(index='date', columns='isin', values='mc').sort_index()
    
    print("Calculating 50 DMA and 200 DMA...")
    dma_50 = price_pivot.rolling(window=50, min_periods=40).mean()
    dma_200 = price_pivot.rolling(window=200, min_periods=180).mean()
    
    print("Calculating Breadth (% above DMA) for Top 1000 dynamically...")
    # Boolean masks for whether a stock is above its DMA
    above_50 = price_pivot > dma_50
    above_200 = price_pivot > dma_200
    
    # Determine the Top 1000 mask dynamically for each day
    # rank(axis=1, ascending=False) ranks market caps from largest (1) to smallest (N)
    top_1000_mask = mc_pivot.rank(axis=1, ascending=False, method='first') <= 1000
    
    # Apply the mask: we only care if a stock is in top 1000 AND above its DMA
    above_50_top1000 = above_50 & top_1000_mask
    above_200_top1000 = above_200 & top_1000_mask
    
    # The denominator is exactly 1000 (or slightly less if fewer than 1000 stocks traded)
    universe_counts = top_1000_mask.sum(axis=1)
    
    breadth_50 = above_50_top1000.sum(axis=1) / universe_counts * 100
    breadth_200 = above_200_top1000.sum(axis=1) / universe_counts * 100
    
    df_breadth = pd.DataFrame({
        'date': price_pivot.index,
        'pct_above_50dma': breadth_50.values,
        'pct_above_200dma': breadth_200.values
    })
    
    df_breadth = df_breadth[df_breadth['date'] >= start_date].copy()
    
    # 3. Merge and Plot
    df_plot = pd.merge(n500[['date', 'close']], df_breadth, on='date', how='inner')
    
    print("Plotting...")
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    color_n500 = 'black'
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Nifty 500 Index', color=color_n500, fontsize=12, fontweight='bold')
    # Use log scale for Nifty 500 as it shows exponential growth better over 10 years
    ax1.plot(df_plot['date'], df_plot['close'], color=color_n500, linewidth=2, label='Nifty 500')
    ax1.set_yscale('log')
    ax1.tick_params(axis='y', labelcolor=color_n500)
    
    # Create secondary y-axis for Breadth %
    ax2 = ax1.twinx()  
    color_50 = 'tab:blue'
    color_200 = 'tab:red'
    
    ax2.set_ylabel('% of Stocks Above DMA', color='dimgray', fontsize=12, fontweight='bold')
    ax2.plot(df_plot['date'], df_plot['pct_above_50dma'], color=color_50, linewidth=1, alpha=0.7, label='% Above 50 DMA')
    ax2.plot(df_plot['date'], df_plot['pct_above_200dma'], color=color_200, linewidth=1.5, alpha=0.8, label='% Above 200 DMA')
    
    ax2.set_ylim(0, 100)
    ax2.tick_params(axis='y', labelcolor='dimgray')
    
    # Draw horizontal lines for typical overbought/oversold extreme breadth levels
    ax2.axhline(20, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(80, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(50, color='black', linestyle=':', alpha=0.3)
    
    # Format X-axis
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    # Legends
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', fontsize=11)
    
    plt.title('Nifty 500 Index vs Market Breadth (50 DMA & 200 DMA)', fontsize=16, fontweight='bold')
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    
    out_path = repo_root / "nifty500_market_breadth.png"
    plt.savefig(out_path, dpi=300)
    print(f"Plot saved successfully to: {out_path}")

if __name__ == "__main__":
    plot_market_breadth()
