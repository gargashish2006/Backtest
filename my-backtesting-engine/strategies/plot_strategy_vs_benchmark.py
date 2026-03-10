
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # File paths
    base_path = Path('.')
    benchmark_path = base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
    
    # Strategy files - using the specific timestamps associated with the latest runs
    strat_3stocks_path = base_path / 'strategies/outputs/industry_4q_10ind_3stocks_equity_20260208_194053.csv'
    strat_2stocks_path = base_path / 'strategies/outputs/industry_4q_10ind_2stocks_equity_20260208_194502.csv'
    strat_2stocks_1000cr_path = base_path / 'strategies/outputs/industry_4q_10ind_2stocks_mcap1000_equity_20260208_194924.csv'
    
    # Load data
    print("Loading data...")
    bench_df = pd.read_csv(benchmark_path)
    strat_3s_df = pd.read_csv(strat_3stocks_path)
    strat_2s_df = pd.read_csv(strat_2stocks_path)
    strat_2s_1000cr_df = pd.read_csv(strat_2stocks_1000cr_path)
    
    # Convert dates
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    strat_3s_df['date'] = pd.to_datetime(strat_3s_df['date'])
    strat_2s_df['date'] = pd.to_datetime(strat_2s_df['date'])
    strat_2s_1000cr_df['date'] = pd.to_datetime(strat_2s_1000cr_df['date'])
    
    # Determine common start date (based on strategy start)
    start_date = strat_3s_df['date'].min()
    print(f"Aligning to start date: {start_date.date()}")
    
    # Filter benchmark to start date
    bench_df = bench_df[bench_df['date'] >= start_date].copy()
    
    # Normalize to 100
    print("Normalizing data...")
    
    # Benchmark normalization
    bench_start_val = bench_df.iloc[0]['index_value']
    bench_df['normalized'] = bench_df['index_value'] / bench_start_val * 100
    
    # Strategies normalization
    strat_3s_df['normalized'] = strat_3s_df['value'] / strat_3s_df.iloc[0]['value'] * 100
    strat_2s_df['normalized'] = strat_2s_df['value'] / strat_2s_df.iloc[0]['value'] * 100
    strat_2s_1000cr_df['normalized'] = strat_2s_1000cr_df['value'] / strat_2s_1000cr_df.iloc[0]['value'] * 100
    
    # Plotting
    print("Generating plot...")
    plt.figure(figsize=(14, 8))
    
    # Plot benchmark
    plt.plot(bench_df['date'], bench_df['normalized'], label='Benchmark (Top 1000 Eq Wt)', color='gray', linestyle='--', alpha=0.7, linewidth=1.5)
    
    # Plot strategies
    plt.plot(strat_3s_df['date'], strat_3s_df['normalized'], label='10 Ind x 3 Stocks (Unrestricted)', color='#1f77b4', linewidth=2.5)
    plt.plot(strat_2s_df['date'], strat_2s_df['normalized'], label='10 Ind x 2 Stocks (Unrestricted)', color='#ff7f0e', linewidth=2.5)
    plt.plot(strat_2s_1000cr_df['date'], strat_2s_1000cr_df['normalized'], label='10 Ind x 2 Stocks (>1000 Cr)', color='#2ca02c', linewidth=2.5)
    
    # Formatting
    plt.title('Performance Comparison: Industry Contrarian Strategies vs Benchmark', fontsize=16, pad=20)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Normalized Value (Start = 100)', fontsize=12)
    plt.grid(True, which='major', linestyle='-', alpha=0.3)
    plt.grid(True, which='minor', linestyle=':', alpha=0.1)
    plt.minorticks_on()
    plt.legend(fontsize=12, loc='upper left')
    
    # Add final values text
    last_date = strat_3s_df['date'].max()
    
    # Get final values using closest date matching potentially
    bench_final = bench_df.iloc[-1]['normalized']
    s3_final = strat_3s_df.iloc[-1]['normalized']
    s2_final = strat_2s_df.iloc[-1]['normalized']
    s2_1000_final = strat_2s_1000cr_df.iloc[-1]['normalized']
    
    plt.annotate(f"{bench_final:.0f}", xy=(bench_df.iloc[-1]['date'], bench_final), xytext=(10, 0), textcoords='offset points', color='gray')
    plt.annotate(f"{s3_final:.0f}", xy=(strat_3s_df.iloc[-1]['date'], s3_final), xytext=(10, 0), textcoords='offset points', color='#1f77b4', fontweight='bold')
    plt.annotate(f"{s2_final:.0f}", xy=(strat_2s_df.iloc[-1]['date'], s2_final), xytext=(10, 0), textcoords='offset points', color='#ff7f0e', fontweight='bold')
    plt.annotate(f"{s2_1000_final:.0f}", xy=(strat_2s_1000cr_df.iloc[-1]['date'], s2_1000_final), xytext=(10, 0), textcoords='offset points', color='#2ca02c', fontweight='bold')

    # Calculate returns for legend/table
    bench_ret = (bench_final/100 - 1) * 100
    s3_ret = (s3_final/100 - 1) * 100
    s2_ret = (s2_final/100 - 1) * 100
    s2_1000_ret = (s2_1000_final/100 - 1) * 100
    
    # Add stats table
    stats_text = (
        f"Total Returns:\n"
        f"Benchmark: {bench_ret:.1f}%\n"
        f"3 Stocks: {s3_ret:.1f}%\n"
        f"2 Stocks: {s2_ret:.1f}%\n"
        f"2 Stocks (>1000Cr): {s2_1000_ret:.1f}%"
    )
    plt.text(0.02, 0.50, stats_text, transform=plt.gca().transAxes, fontsize=10, 
             bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

    # Save plot
    output_file = base_path / 'strategies/outputs/strategy_comparison_with_benchmark.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
if __name__ == "__main__":
    main()
