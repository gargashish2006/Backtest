import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
import glob
import os

def plot_performance():
    # Paths
    base_path = Path(__file__).parent.parent.parent
    strategy_outputs = base_path / 'strategies/industry_group/outputs'
    benchmark_file = base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
    
    # 1. Load Strategy Data (Latest Monthly Exit)
    strategy_files = glob.glob(str(strategy_outputs / 'hierarchical_60_absolute_rs_monthly_exit_equity_*.csv'))
    if not strategy_files:
        print("No strategy files found!")
        return
    latest_strategy_file = max(strategy_files, key=os.path.getmtime)
    print(f"Loading Strategy: {latest_strategy_file}")
    df_strat = pd.read_csv(latest_strategy_file)
    df_strat['date'] = pd.to_datetime(df_strat['date'])
    
    # 2. Load Benchmark Data
    df_bench = pd.read_csv(benchmark_file)
    df_bench['date'] = pd.to_datetime(df_bench['date'])
    
    # Merge and Normalize
    df = pd.merge(df_strat, df_bench[['date', 'index_value']], on='date', how='inner')
    df = df.sort_values('date')
    
    df['strategy_nav'] = df['value'] / df['value'].iloc[0] * 100
    df['benchmark_nav'] = df['index_value'] / df['index_value'].iloc[0] * 100
    
    # Metrics
    strat_ret = (df['strategy_nav'].iloc[-1] / df['strategy_nav'].iloc[0] - 1) * 100
    bench_ret = (df['benchmark_nav'].iloc[-1] / df['benchmark_nav'].iloc[0] - 1) * 100
    
    # Plotting
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(15, 8))
    
    ax.plot(df['date'], df['strategy_nav'], color='#00ff99', linewidth=2.5, label=f'Monthly Exit + Reinvest Strategy ({strat_ret:.0f}%)')
    ax.plot(df['date'], df['benchmark_nav'], color='#888888', linewidth=1.5, linestyle='--', label=f'Top 1000 Benchmark ({bench_ret:.0f}%)')
    
    # Formatting
    ax.set_title('Monthly Exit + Reinvest vs Top 1000 Benchmark', fontsize=18, fontweight='bold', pad=20, color='white')
    ax.set_xlabel('Date', fontsize=12, labelpad=10)
    ax.set_ylabel('NAV (Base 100)', fontsize=12, labelpad=10)
    
    ax.legend(fontsize=12, frameon=True, facecolor='#222222', edgecolor='#444444')
    ax.grid(True, which='both', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    output_plot = base_path / 'analysis/outputs/plots/performance_monthly_exit_vs_top1000.png'
    output_plot.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_plot, dpi=300)
    print(f"Plot saved to: {output_plot}")
    
    plt.show()

if __name__ == "__main__":
    plot_performance()
