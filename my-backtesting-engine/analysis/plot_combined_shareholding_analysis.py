#!/usr/bin/env python
"""
Combined Shareholding Analysis Plot

Plots both:
1. % of stocks with increasing market cap per shareholder (QoQ)
2. % of stocks with increasing number of shareholders (QoQ)

on the same chart for comparison.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys


def plot_combined_analysis():
    """Plot both metrics together for comparison"""
    
    # Load the data files
    reports_dir = Path(__file__).parent / 'outputs' / 'reports'
    
    # Load market cap per shareholder data
    mcap_file = reports_dir / 'shareholding_qoq_change_analysis.csv'
    shareholder_file = reports_dir / 'shareholder_count_change_analysis.csv'
    
    if not mcap_file.exists():
        print(f"Error: {mcap_file} not found!")
        print("Please run 'python analysis/shareholding_qoq_change_analysis.py' first.")
        sys.exit(1)
    
    if not shareholder_file.exists():
        print(f"Error: {shareholder_file} not found!")
        print("Please run 'python analysis/shareholder_count_change_analysis.py' first.")
        sys.exit(1)
    
    # Read data
    mcap_df = pd.read_csv(mcap_file)
    mcap_df['quarter_date'] = pd.to_datetime(mcap_df['quarter_date'])
    
    shareholder_df = pd.read_csv(shareholder_file)
    shareholder_df['quarter_date'] = pd.to_datetime(shareholder_df['quarter_date'])
    
    # Merge on quarter_date (inner join to get common quarters only)
    merged = mcap_df.merge(
        shareholder_df[['quarter_date', 'pct_increasing', 'num_compared']],
        on='quarter_date',
        how='inner',
        suffixes=('_mcap', '_shareholders')
    )
    
    print(f"Plotting data for {len(merged)} common quarters...")
    print(f"Period: {merged['quarter_date'].min().date()} to {merged['quarter_date'].max().date()}")
    
    # Create figure with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12))
    
    # Plot 1: Both metrics on same chart
    ax1.plot(merged['quarter_date'], merged['pct_increasing_mcap'],
            linewidth=2.5,
            marker='o',
            markersize=6,
            color='#2E86AB',
            label='% Stocks: Increasing Market Cap per Shareholder',
            alpha=0.8)
    
    ax1.plot(merged['quarter_date'], merged['pct_increasing_shareholders'],
            linewidth=2.5,
            marker='s',
            markersize=6,
            color='#E63946',
            label='% Stocks: Increasing Number of Shareholders',
            alpha=0.8)
    
    # Add 50% reference line
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, linewidth=1.5, label='50% (Equilibrium)')
    
    ax1.set_xlabel('Quarter', fontsize=11, fontweight='bold')
    ax1.set_ylabel('% of Stocks', fontsize=11, fontweight='bold')
    ax1.set_title('Shareholding Pattern Comparison: Market Cap per Shareholder vs Number of Shareholders (QoQ)',
                 fontsize=13, fontweight='bold', pad=15)
    ax1.set_ylim(0, 100)
    ax1.legend(loc='best', fontsize=10, framealpha=0.9)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Plot 2: Difference between the two metrics
    merged['difference'] = merged['pct_increasing_mcap'] - merged['pct_increasing_shareholders']
    
    colors = ['green' if x >= 0 else 'red' for x in merged['difference']]
    ax2.bar(merged['quarter_date'], merged['difference'],
           color=colors,
           alpha=0.7,
           edgecolor='black',
           linewidth=0.5)
    
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1.5)
    ax2.set_xlabel('Quarter', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Difference (% points)', fontsize=11, fontweight='bold')
    ax2.set_title('Concentration vs Participation: Difference Between Metrics\n(Positive = More concentration, Negative = More participation)',
                 fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='y')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add annotation for interpretation
    ax2.text(0.02, 0.97, 
             'Green: Wealth concentrating (fewer but wealthier shareholders)\n'
             'Red: Broader participation (more shareholders joining)',
             transform=ax2.transAxes,
             fontsize=9,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Plot 3: Correlation scatter plot (recent 20 quarters)
    recent = merged.tail(20)
    ax3.scatter(recent['pct_increasing_shareholders'], recent['pct_increasing_mcap'],
               s=100,
               alpha=0.6,
               c=range(len(recent)),
               cmap='viridis',
               edgecolors='black',
               linewidth=1)
    
    # Add trend line
    z = np.polyfit(recent['pct_increasing_shareholders'], recent['pct_increasing_mcap'], 1)
    p = np.poly1d(z)
    x_trend = np.linspace(recent['pct_increasing_shareholders'].min(), 
                         recent['pct_increasing_shareholders'].max(), 100)
    ax3.plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2, label=f'Trend: y={z[0]:.2f}x+{z[1]:.2f}')
    
    # Add reference lines
    ax3.axhline(y=50, color='gray', linestyle='--', alpha=0.3, linewidth=1)
    ax3.axvline(x=50, color='gray', linestyle='--', alpha=0.3, linewidth=1)
    
    ax3.set_xlabel('% Stocks: Increasing Number of Shareholders', fontsize=11, fontweight='bold')
    ax3.set_ylabel('% Stocks: Increasing Market Cap per Shareholder', fontsize=11, fontweight='bold')
    ax3.set_title('Correlation Analysis (Last 20 Quarters)\nDarker points = More recent',
                 fontsize=13, fontweight='bold', pad=15)
    ax3.set_xlim(0, 100)
    ax3.set_ylim(0, 100)
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # Add quadrant labels
    ax3.text(75, 75, 'Both\nIncreasing', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
    ax3.text(25, 75, 'Concentration\nWithout Growth', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
    ax3.text(75, 25, 'Participation\nWithout Value', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
    ax3.text(25, 25, 'Both\nDecreasing', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
    
    plt.tight_layout()
    
    # Save plot
    output_path = reports_dir / 'combined_shareholding_analysis_plot.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✅ Plot saved to: {output_path}")
    
    plt.show()
    
    # Print statistics
    print("\n" + "="*80)
    print("COMBINED ANALYSIS STATISTICS")
    print("="*80)
    
    print(f"\nPeriod: {merged['quarter_date'].min().date()} to {merged['quarter_date'].max().date()}")
    print(f"Quarters Analyzed: {len(merged)}")
    
    print(f"\nMarket Cap per Shareholder Increase:")
    print(f"  Average: {merged['pct_increasing_mcap'].mean():.1f}%")
    print(f"  Median:  {merged['pct_increasing_mcap'].median():.1f}%")
    
    print(f"\nNumber of Shareholders Increase:")
    print(f"  Average: {merged['pct_increasing_shareholders'].mean():.1f}%")
    print(f"  Median:  {merged['pct_increasing_shareholders'].median():.1f}%")
    
    print(f"\nDifference (Concentration - Participation):")
    print(f"  Average: {merged['difference'].mean():.1f} percentage points")
    print(f"  Median:  {merged['difference'].median():.1f} percentage points")
    
    # Correlation
    correlation = merged['pct_increasing_mcap'].corr(merged['pct_increasing_shareholders'])
    print(f"\nCorrelation between metrics: {correlation:.3f}")
    
    if correlation > 0.5:
        print("  → Strong positive correlation: Both metrics move together")
    elif correlation > 0:
        print("  → Weak positive correlation: Some tendency to move together")
    elif correlation > -0.5:
        print("  → Weak negative correlation: Some tendency to move opposite")
    else:
        print("  → Strong negative correlation: Metrics move in opposite directions")
    
    # Recent trend
    print("\nRecent Values (Last 5 quarters):")
    print("-"*80)
    print(f"{'Quarter':<12} | {'MCap/SH %':>10} | {'#SH %':>10} | {'Difference':>12}")
    print("-"*80)
    for _, row in merged.tail(5).iterrows():
        diff_sign = "+" if row['difference'] >= 0 else ""
        print(f"{row['quarter_date'].date()} | {row['pct_increasing_mcap']:>9.1f}% | {row['pct_increasing_shareholders']:>9.1f}% | {diff_sign}{row['difference']:>10.1f} pts")
    
    print("="*80)
    
    # Save combined CSV
    output_csv = reports_dir / 'combined_shareholding_analysis.csv'
    merged.to_csv(output_csv, index=False)
    print(f"\n✅ Combined data saved to: {output_csv}")


if __name__ == "__main__":
    import numpy as np
    
    print("="*80)
    print("COMBINED SHAREHOLDING ANALYSIS")
    print("="*80)
    
    plot_combined_analysis()
