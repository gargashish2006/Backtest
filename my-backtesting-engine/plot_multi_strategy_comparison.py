#!/usr/bin/env python
"""
Plot NAV comparison between multiple strategies and top 1000 benchmark
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def plot_multi_strategy_comparison():
    """Plot NAV comparison between multiple strategies and benchmark"""

    base_path = Path(__file__).parent

    # Load all strategy equity data
    strategies = {
        'Original (All-Cap, 30 stocks)': base_path / 'strategies' / 'outputs' / 'industry_4q_10ind_3stocks_equity_20260208_135757.csv',
        'Top 1000 Final Selection (30 stocks)': base_path / 'strategies' / 'outputs' / 'industry_4q_10ind_3stocks_equity_20260208_141656.csv',
        'Top 1000 Universe (30 stocks)': base_path / 'strategies' / 'outputs' / 'industry_4q_10ind_3stocks_equity_20260208_140539.csv',
        'Top 1000 Universe (20 stocks)': base_path / 'strategies' / 'outputs' / 'industry_4q_10ind_3stocks_equity_20260208_140747.csv'
    }

    # Load benchmark data
    benchmark_file = base_path / 'analysis' / 'outputs' / 'benchmarks' / 'benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
    benchmark_df = pd.read_csv(benchmark_file)
    benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
    benchmark_df = benchmark_df.set_index('date')

    # Load and process strategies
    strategy_data = {}
    for name, file_path in strategies.items():
        df = pd.read_csv(file_path)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        strategy_data[name] = df

    # Filter to common date range (May 2017 onwards)
    start_date = pd.to_datetime('2017-05-01')

    # Filter benchmark to start date
    benchmark_df = benchmark_df.loc[start_date:]

    # Normalize all to start at 100
    normalized_data = {}

    # Normalize benchmark
    benchmark_start_value = benchmark_df['index_value'].iloc[0]
    normalized_data['Top 1000 Equal Weight Benchmark'] = (benchmark_df['index_value'] / benchmark_start_value) * 100

    # Normalize strategies
    for name, df in strategy_data.items():
        strategy_start_value = df['value'].iloc[0]
        normalized_data[name] = (df['value'] / strategy_start_value) * 100

    # Create plot
    fig, ax = plt.subplots(figsize=(16, 10))

    # Color scheme
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    linestyles = ['-', '--', '-.', ':']

    # Plot all series
    for i, (name, data) in enumerate(normalized_data.items()):
        ax.plot(data.index, data.values,
                label=name, linewidth=2.5, color=colors[i % len(colors)],
                linestyle=linestyles[i % len(linestyles)])

    # Formatting
    ax.set_title('Strategy Performance Comparison: Contrarian Strategies vs Top 1000 Benchmark\n(May 2017 - Nov 2025)',
                fontsize=16, fontweight='bold', pad=20)
    ax.set_ylabel('Normalized Value (Base = 100)', fontsize=14)
    ax.set_xlabel('Date', fontsize=14)
    ax.legend(fontsize=12, loc='upper left')
    ax.grid(True, alpha=0.3)

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0f}'))

    # Add final values as annotations
    for i, (name, data) in enumerate(normalized_data.items()):
        final_value = data.iloc[-1]
        # Position annotations to avoid overlap
        y_pos = final_value + (i * 5)  # Slight vertical offset
        ax.annotate(f'{final_value:.0f}', xy=(data.index[-1], final_value),
                   xytext=(10, 0), textcoords='offset points',
                   fontsize=11, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=colors[i % len(colors)], alpha=0.8))

    plt.tight_layout()

    # Save plot
    output_file = base_path / 'strategies' / 'outputs' / 'multi_strategy_vs_benchmark_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to: {output_file}")

    # Show plot
    plt.show()

if __name__ == '__main__':
    plot_multi_strategy_comparison()