
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # File paths
    base_path = Path('.')
    # Use the Top 500 Benchmark
    benchmark_path = base_path / 'analysis/outputs/benchmarks/benchmark_top500_equal_weight_2016-02-01_to_2026-01-28.csv'
    
    # Strategy file - Top 500 Variation
    strat_top500_path = base_path / 'strategies/outputs/industry_4q_10ind_2stocks_top500_equity_20260208_200603.csv'
    
    # Load data
    print("Loading data...")
    bench_df = pd.read_csv(benchmark_path)
    strat_top500_df = pd.read_csv(strat_top500_path)
    
    # Convert dates
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    strat_top500_df['date'] = pd.to_datetime(strat_top500_df['date'])
    
    # Determine common start date (based on strategy start)
    start_date = strat_top500_df['date'].min()
    print(f"Aligning to start date: {start_date.date()}")
    
    # Filter benchmark to start date
    bench_df = bench_df[bench_df['date'] >= start_date].copy()
    
    # Normalize to 100
    print("Normalizing data...")
    
    # Benchmark normalization
    bench_start_val = bench_df.iloc[0]['index_value']
    bench_df['normalized'] = bench_df['index_value'] / bench_start_val * 100
    
    # Strategy normalization
    strat_top500_df['normalized'] = strat_top500_df['value'] / strat_top500_df.iloc[0]['value'] * 100
    
    # Plotting
    print("Generating plot...")
    plt.figure(figsize=(14, 8))
    
    # Plot benchmark
    plt.plot(bench_df['date'], bench_df['normalized'], label='Benchmark (Top 500 Eq Wt)', color='gray', linestyle='--', alpha=0.7, linewidth=1.5)
    
    # Plot strategy
    plt.plot(strat_top500_df['date'], strat_top500_df['normalized'], label='Strategy (Top 500 Stocks Only)', color='#d62728', linewidth=2.5)
    
    # Formatting
    plt.title('Performance Comparison: Top 500 Strategy vs Top 500 Benchmark', fontsize=16, pad=20)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Normalized Value (Start = 100)', fontsize=12)
    plt.grid(True, which='major', linestyle='-', alpha=0.3)
    plt.grid(True, which='minor', linestyle=':', alpha=0.1)
    plt.minorticks_on()
    plt.legend(fontsize=12, loc='upper left')
    
    # Add final values text
    bench_final = bench_df.iloc[-1]['normalized']
    strat_final = strat_top500_df.iloc[-1]['normalized']
    
    plt.annotate(f"{bench_final:.0f}", xy=(bench_df.iloc[-1]['date'], bench_final), xytext=(10, 0), textcoords='offset points', color='gray')
    plt.annotate(f"{strat_final:.0f}", xy=(strat_top500_df.iloc[-1]['date'], strat_final), xytext=(10, 0), textcoords='offset points', color='#d62728', fontweight='bold')

    # Calculate returns for legend/table
    bench_ret = (bench_final/100 - 1) * 100
    strat_ret = (strat_final/100 - 1) * 100
    
    # Add stats table
    stats_text = (
        f"Total Returns:\n"
        f"Benchmark (Top 500): {bench_ret:.1f}%\n"
        f"Strategy (Top 500): {strat_ret:.1f}%"
    )
    plt.text(0.02, 0.50, stats_text, transform=plt.gca().transAxes, fontsize=10, 
             bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

    # Save plot
    output_file = base_path / 'strategies/outputs/strategy_top500_vs_benchmark.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
if __name__ == "__main__":
    main()
