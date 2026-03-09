import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import sys

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

from data.data_handler import DataHandler

def plot_highest_close():
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
    
    # 2. Pivot prices and market caps (adding buffer for 200 day roll)
    print("Pivoting data...")
    df_p = dh.price_df[dh.price_df['date'] >= (start_date - pd.Timedelta(days=400))] 
    
    price_pivot = df_p.pivot(index='date', columns='isin', values='close').sort_index()
    mc_pivot = df_p.pivot(index='date', columns='isin', values='mc').sort_index()
    
    # Determine the Top 1000 mask dynamically for each day
    print("Computing dynamic Top 1000 mask...")
    top_1000_mask = mc_pivot.rank(axis=1, ascending=False, method='first') <= 1000
    universe_counts = top_1000_mask.sum(axis=1)
    
    print("Calculating rolling highest closes...")
    windows = [20, 200]
    breadth_data = {'date': price_pivot.index}
    
    for w in windows:
        # Calculate the rolling maximum over window 'w'
        rolling_max = price_pivot.rolling(window=w, min_periods=max(1, w//2)).max()
        
        # A stock is making an N-day highest close if its current close is >= the rolling max 
        # (Using >= handles exact float matches, essentially highest close within the last W days)
        # Note: If today's price is the absolute highest in the rolling window it will equal the rolling window max.
        is_highest = price_pivot >= rolling_max
        
        # Apply Top 1000 mask
        highest_top1000 = is_highest & top_1000_mask
        
        # Calculate percentage
        pct_highest = (highest_top1000.sum(axis=1) / universe_counts) * 100
        breadth_data[f'high_{w}c'] = pct_highest.values
        print(f"Computed {w}-day highest close breadth.")

    df_breadth = pd.DataFrame(breadth_data)
    df_breadth = df_breadth[df_breadth['date'] >= start_date].copy()
    
    # 3. Merge and Plot
    df_plot = pd.merge(n500[['date', 'close']], df_breadth, on='date', how='inner')
    
    print("Plotting...")
    # Create a figure with 2 subplots (Nifty 500 on top, Breadths on bottom) to avoid crowding
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
    
    # Plot 1: Nifty 500
    color_n500 = 'black'
    ax1.set_ylabel('Nifty 500 Index (Log Scale)', color=color_n500, fontsize=12, fontweight='bold')
    ax1.plot(df_plot['date'], df_plot['close'], color=color_n500, linewidth=2, label='Nifty 500')
    ax1.set_yscale('log')
    ax1.tick_params(axis='y', labelcolor=color_n500)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=12)
    ax1.set_title('Nifty 500 Index vs Market Breadth (% of Top 1000 Stocks Making N-Day Highest Close)', fontsize=14, fontweight='bold')
    
    # Plot 2: Breadth Lines
    colors = {20: 'orange', 200: 'firebrick'}
    ax2.set_ylabel('% of Stocks', color='dimgray', fontsize=12, fontweight='bold')
    
    for w in windows:
        ax2.plot(df_plot['date'], df_plot[f'high_{w}c'], color=colors[w], linewidth=1.5, alpha=0.8, label=f'{w}-Day Highest Close')
        
    ax2.set_ylim(0, max(df_plot['high_20c'].max(), 30) + 5) # Scale to fit the highest peak (usually short term)
    ax2.tick_params(axis='y', labelcolor='dimgray')
    
    # Draw horizontal lines for typical breadth levels
    ax2.axhline(10, color='gray', linestyle='--', alpha=0.3)
    ax2.axhline(20, color='gray', linestyle='--', alpha=0.3)
    
    ax2.set_xlabel('Date', fontsize=12)
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax2.legend(loc='upper left', fontsize=11, ncol=4)
    ax2.grid(True, alpha=0.2)
    
    plt.tight_layout()
    
    out_path = repo_root / "nifty500_highest_close_breadth.png"
    plt.savefig(out_path, dpi=300)
    print(f"Plot saved successfully to: {out_path}")

if __name__ == "__main__":
    plot_highest_close()
