
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # File paths
    base_path = Path('.')
    benchmark_path = base_path / 'analysis/outputs/benchmarks/benchmark_top500_equal_weight_2016-02-01_to_2026-01-28.csv'
    
    # Strategy Files (Best 5)
    files = {
        'Original (3 Stocks/Ind)': base_path / 'strategies/outputs/industry_4q_10ind_3stocks_equity_20260208_194053.csv',
        'Modified (2 Stocks/Ind)': base_path / 'strategies/outputs/industry_4q_10ind_2stocks_equity_20260208_194502.csv',
        'Hierarchical (Groups->Inds)': base_path / 'strategies/industry_group/outputs/hierarchical_contrarian_trend_equity_20260208_202641.csv',
        'Dynamic Top 500 (20 Stocks)': base_path / 'strategies/outputs/industry_4q_10ind_2stocks_top500_dynamic_equity_20260208_201120.csv',
        'Static >1000Cr (2 Stocks)': base_path / 'strategies/outputs/industry_4q_10ind_2stocks_mcap1000_equity_20260208_194924.csv'
    }
    
    # Colors for plot
    colors = {
        'Original (3 Stocks/Ind)': '#1f77b4',  # Blue
        'Modified (2 Stocks/Ind)': '#ff7f0e',  # Orange
        'Hierarchical (Groups->Inds)': '#2ca02c', # Green
        'Dynamic Top 500 (20 Stocks)': '#d62728', # Red
        'Static >1000Cr (2 Stocks)': '#9467bd'   # Purple
    }

    # Load Benchmark
    print("Loading benchmark...")
    if benchmark_path.exists():
        bench_df = pd.read_csv(benchmark_path)
        bench_df['date'] = pd.to_datetime(bench_df['date'])
    else:
        print("Benchmark file not found!")
        bench_df = None

    # Load Strategies
    print("Loading strategies...")
    dfs = {}
    for name, path in files.items():
        if path.exists():
            df = pd.read_csv(path)
            df['date'] = pd.to_datetime(df['date'])
            dfs[name] = df
        else:
            print(f"Warning: File not found for {name}: {path}")

    if not dfs:
        print("No strategy files found.")
        return

    # Determine common start date (max of min dates)
    start_date = max([df['date'].min() for df in dfs.values()])
    print(f"Aligning all strategies to start date: {start_date.date()}")
    
    # Filter and Normalize
    plt.figure(figsize=(14, 9))
    
    # Plot Benchmark
    if bench_df is not None:
        bench_df = bench_df[bench_df['date'] >= start_date].copy()
        if not bench_df.empty:
            start_val = bench_df.iloc[0]['index_value']
            bench_df['normalized'] = bench_df['index_value'] / start_val * 100
            final_val = bench_df.iloc[-1]['normalized']
            plt.plot(bench_df['date'], bench_df['normalized'], label=f'Benchmark (Top 500) [{final_val:.0f}]', 
                     color='gray', linestyle='--', alpha=0.6, linewidth=1.5)

    # Plot Strategies
    stats = []
    
    for name, df in dfs.items():
        df_filtered = df[df['date'] >= start_date].copy()
        if df_filtered.empty: continue
        
        start_val = df_filtered.iloc[0]['value']
        df_filtered['normalized'] = df_filtered['value'] / start_val * 100
        
        final_norm = df_filtered.iloc[-1]['normalized']
        total_ret = (final_norm/100 - 1) * 100
        
        # Calculate Sharpe (simple approximation for sorting)
        returns = df_filtered['value'].pct_change().dropna()
        sharpe = returns.mean() / returns.std() * (4**0.5) if returns.std() > 0 else 0
        
        # Calculate Max Drawdown
        dd = (df_filtered['value'] - df_filtered['value'].cummax()) / df_filtered['value'].cummax() * 100
        max_dd = dd.min()
        
        stats.append({
            'Strategy': name,
            'Return': total_ret,
            'Sharpe': sharpe,
            'Drawdown': max_dd,
            'Final_Norm': final_norm
        })
        
        plt.plot(df_filtered['date'], df_filtered['normalized'], label=f"{name}", 
                 color=colors.get(name, 'black'), linewidth=2.0)
        
        # Add annotation at the end
        plt.annotate(f"{final_norm:.0f}", 
                     xy=(df_filtered.iloc[-1]['date'], final_norm), 
                     xytext=(10, 0), textcoords='offset points', 
                     color=colors.get(name, 'black'), fontweight='bold', fontsize=9)

    # Formatting
    plt.title('Performance Comparison: Top 5 Strategies vs Benchmark', fontsize=16, pad=20)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Normalized Value (Start = 100)', fontsize=12)
    plt.grid(True, which='major', linestyle='-', alpha=0.3)
    plt.grid(True, which='minor', linestyle=':', alpha=0.1)
    plt.minorticks_on()
    plt.legend(fontsize=11, loc='upper left')
    
    # Add stats table to plot
    stats_df = pd.DataFrame(stats).sort_values('Return', ascending=False)
    
    table_text = "Strategy Metrics:\n"
    table_text += "-"*35 + "\n"
    for _, row in stats_df.iterrows():
        table_text += f"{row['Strategy'][:25]}:\n"
        table_text += f"  Ret: {row['Return']:.1f}% | DD: {row['Drawdown']:.1f}%\n"
        table_text += "-"*35 + "\n"
        
    plt.text(0.02, 0.35, table_text, transform=plt.gca().transAxes, fontsize=9, 
             bbox=dict(facecolor='white', alpha=0.9, boxstyle='round'), family='monospace')

    # Save plot
    output_file = base_path / 'strategies/outputs/comparison_top_5_strategies.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
    # Print stats for verification
    print("\nComparison Stats:")
    print(stats_df.to_string(index=False))

if __name__ == "__main__":
    main()
