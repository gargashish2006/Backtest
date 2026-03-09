import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

def plot_nav():
    # Load CS15 NAV
    nav_file = repo_root / "cs15_nav.csv"
    if not nav_file.exists():
        print(f"Error: {nav_file} not found. Please run CS15 backtest first.")
        return
        
    df_nav = pd.read_csv(nav_file)
    df_nav['date'] = pd.to_datetime(df_nav['date'])
    df_nav = df_nav.sort_values('date')
    
    # Calculate CS15 NAV scaled to 100 at start
    start_val = df_nav['nav'].iloc[0]
    df_nav['nav_scaled'] = (df_nav['nav'] / start_val) * 100
    
    # Load Nifty 500
    indices_file = repo_root / "database/indices_data.parquet"
    if not indices_file.exists():
        print(f"Error: {indices_file} not found.")
        return
        
    df_idx = pd.read_parquet(indices_file)
    df_n500 = df_idx[df_idx['index_name'] == 'NIFTY 500'].copy()
    df_n500['date'] = pd.to_datetime(df_n500['date'])
    df_n500 = df_n500.sort_values('date')
    
    # Merge on date to align
    df_merged = pd.merge(df_nav[['date', 'nav_scaled']], df_n500[['date', 'close']], on='date', how='inner')
    
    if df_merged.empty:
        print("No overlapping dates found between CS15 NAV and Nifty 500.")
        return
        
    # Scale Nifty 500 to 100 at the first overlapping date
    n500_start_val = df_merged['close'].iloc[0]
    df_merged['nifty500_scaled'] = (df_merged['close'] / n500_start_val) * 100
    
    # Calculate final returns for the legend
    cs15_return = (df_merged['nav_scaled'].iloc[-1] / 100 - 1) * 100
    n500_return = (df_merged['nifty500_scaled'].iloc[-1] / 100 - 1) * 100
    
    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(df_merged['date'], df_merged['nav_scaled'], label=f'CS15 (Return: {cs15_return:.2f}%)', color='blue', linewidth=2)
    plt.plot(df_merged['date'], df_merged['nifty500_scaled'], label=f'Nifty 500 (Return: {n500_return:.2f}%)', color='orange', linewidth=2, alpha=0.8)
    
    plt.title('CS15 Strategy vs Nifty 500 Index (Base 100)', fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Normalized Value (Base 100)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left', fontsize=12)
    plt.tight_layout()
    
    # Save the plot
    out_path = repo_root / "cs15_vs_nifty500.png"
    plt.savefig(out_path, dpi=300)
    print(f"Plot saved to {out_path}")
    
if __name__ == "__main__":
    plot_nav()
