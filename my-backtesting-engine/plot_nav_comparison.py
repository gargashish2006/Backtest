#!/usr/bin/env python
"""
Plot NAV comparison between strategy and top 1000 benchmark
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def plot_nav_comparison():
    """Plot NAV comparison between strategy and benchmark"""

    base_path = Path(__file__).parent

    # Load strategy equity data
    strategy_file = base_path / 'strategies' / 'outputs' / 'industry_4q_10ind_3stocks_equity_20260208_135757.csv'
    strategy_df = pd.read_csv(strategy_file)
    strategy_df['date'] = pd.to_datetime(strategy_df['date'])
    strategy_df = strategy_df.set_index('date')

    # Load benchmark data
    benchmark_file = base_path / 'analysis' / 'outputs' / 'benchmarks' / 'benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.csv'
    benchmark_df = pd.read_csv(benchmark_file)
    benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
    benchmark_df = benchmark_df.set_index('date')

    # Filter to strategy date range
    start_date = strategy_df.index.min()
    end_date = strategy_df.index.max()

    benchmark_df = benchmark_df.loc[start_date:end_date]

    # Normalize both to start at 100
    strategy_start_value = strategy_df['value'].iloc[0]
    benchmark_start_value = benchmark_df['index_value'].iloc[0]

    strategy_normalized = (strategy_df['value'] / strategy_start_value) * 100
    benchmark_normalized = (benchmark_df['index_value'] / benchmark_start_value) * 100

    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot both series
    ax.plot(strategy_normalized.index, strategy_normalized.values,
            label='10×3 Contrarian Strategy', linewidth=2, color='#1f77b4')
    ax.plot(benchmark_normalized.index, benchmark_normalized.values,
            label='Top 1000 Equal Weight Benchmark', linewidth=2, color='#ff7f0e', alpha=0.8)

    # Formatting
    ax.set_title('NAV Comparison: 10×3 Contrarian Strategy vs Top 1000 Benchmark\n(2017-05-01 to 2025-11-01)',
                fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel('Normalized Value (Base = 100)', fontsize=12)
    ax.set_xlabel('Date', fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Format y-axis as percentage
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0f}'))

    # Add final values as text
    final_strategy = strategy_normalized.iloc[-1]
    final_benchmark = benchmark_normalized.iloc[-1]

    ax.text(0.02, 0.98, '.0f',
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='#1f77b4', alpha=0.1))

    ax.text(0.02, 0.92, '.0f',
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='#ff7f0e', alpha=0.1))

    plt.tight_layout()

    # Save plot
    output_file = base_path / 'strategies' / 'outputs' / 'nav_comparison_10x3_vs_top1000.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to: {output_file}")

    # Show plot
    plt.show()

if __name__ == '__main__':
    plot_nav_comparison()