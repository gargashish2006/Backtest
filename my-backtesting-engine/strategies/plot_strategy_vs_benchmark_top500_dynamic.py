
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # File paths
    base_path = Path('.')
    benchmark_path = base_path / 'analysis/outputs/benchmarks/benchmark_top500_equal_weight_2016-02-01_to_2026-01-28.csv'
    
    # Strategy files
    strat_static_path = base_path / 'strategies/outputs/industry_4q_10ind_2stocks_top500_equity_20260208_200603.csv'
    strat_dynamic_path = base_path / 'strategies/outputs/industry_4q_10ind_2stocks_top500_dynamic_equity_20260208_201120.csv'
    
    # Load data
    print("Loading data...")
    bench_df = pd.read_csv(benchmark_path)
    strat_static_df = pd.read_csv(strat_static_path)
    strat_dynamic_df = pd.read_csv(strat_dynamic_path)
    
    # Convert dates
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    strat_static_df['date'] = pd.to_datetime(strat_static_df['date'])
    strat_dynamic_df['date'] = pd.to_datetime(strat_dynamic_df['date'])
    
    # Determine common start date (based on strategy start)
    start_date = strat_static_df['date'].min()
    print(f"Aligning to start date: {start_date.date()}")
    
    # Filter benchmark to start date
    bench_df = bench_df[bench_df['date'] >= start_date].copy()
    
    # Normalize to 100
    print("Normalizing data...")
    
    # Benchmark normalization
    bench_start_val = bench_df.iloc[0]['index_value']
    bench_df['normalized'] = bench_df['index_value'] / bench_start_val * 100
    
    # Strategy normalization
    strat_static_df['normalized'] = strat_static_df['value'] / strat_static_df.iloc[0]['value'] * 100
    strat_dynamic_df['normalized'] = strat_dynamic_df['value'] / strat_dynamic_df.iloc[0]['value'] * 100
    
    # Plotting
    print("Generating plot...")
    plt.figure(figsize=(14, 8))
    
    # Plot benchmark
    plt.plot(bench_df['date'], bench_df['normalized'], label='Benchmark (Top 500 Eq Wt)', color='gray', linestyle='--', alpha=0.7, linewidth=1.5)
    
    # Plot strategies
    plt.plot(strat_static_df['date'], strat_static_df['normalized'], label='Static Top 500 (10 Ind)', color='#7f7f7f', linewidth=2.0, linestyle='-')
    plt.plot(strat_dynamic_df['date'], strat_dynamic_df['normalized'], label='Dynamic Top 500 (Target 20)', color='#9467bd', linewidth=2.5)
    
    # Formatting
    plt.title('Performance Comparison: Top 500 Dynamic Expansion vs Static', fontsize=16, pad=20)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Normalized Value (Start = 100)', fontsize=12)
    plt.grid(True, which='major', linestyle='-', alpha=0.3)
    plt.grid(True, which='minor', linestyle=':', alpha=0.1)
    plt.minorticks_on()
    plt.legend(fontsize=12, loc='upper left')
    
    # Add final values text
    bench_final = bench_df.iloc[-1]['normalized']
    static_final = strat_static_df.iloc[-1]['normalized']
    dynamic_final = strat_dynamic_df.iloc[-1]['normalized']
    
    plt.annotate(f"{bench_final:.0f}", xy=(bench_df.iloc[-1]['date'], bench_final), xytext=(10, 0), textcoords='offset points', color='gray')
    plt.annotate(f"{static_final:.0f}", xy=(strat_static_df.iloc[-1]['date'], static_final), xytext=(10, -10), textcoords='offset points', color='#7f7f7f', fontweight='bold')
    plt.annotate(f"{dynamic_final:.0f}", xy=(strat_dynamic_df.iloc[-1]['date'], dynamic_final), xytext=(10, 0), textcoords='offset points', color='#9467bd', fontweight='bold')

    # Calculate returns for legend/table
    bench_ret = (bench_final/100 - 1) * 100
    static_ret = (static_final/100 - 1) * 100
    dynamic_ret = (dynamic_final/100 - 1) * 100
    
    # Add stats table
    stats_text = (
        f"Total Returns:\n"
        f"Benchmark: {bench_ret:.1f}%\n"
        f"Static Top 500: {static_ret:.1f}%\n"
        f"Dynamic Top 500: {dynamic_ret:.1f}%"
    )
    plt.text(0.02, 0.50, stats_text, transform=plt.gca().transAxes, fontsize=10, 
             bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

    # Save plot
    output_file = base_path / 'strategies/outputs/strategy_top500_dynamic_vs_static.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    
if __name__ == "__main__":
    main()
