#!/usr/bin/env python
"""
Plot Market Breadth Analysis Results
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

def plot_market_breadth(csv_path):
    """Plot market breadth results from CSV file"""
    
    # Read the data
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot both lines
    ax.plot(df['date'], df['top_100_pct'], 
            label='Top 100 Stocks', 
            linewidth=2, 
            marker='o', 
            markersize=4,
            color='#2E86AB')
    
    ax.plot(df['date'], df['top_1000_pct'], 
            label='Top 1000 Stocks', 
            linewidth=2, 
            marker='s', 
            markersize=4,
            color='#A23B72')
    
    # Add horizontal reference lines
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    ax.axhline(y=75, color='green', linestyle='--', alpha=0.3, linewidth=1)
    ax.axhline(y=25, color='red', linestyle='--', alpha=0.3, linewidth=1)
    
    # Formatting
    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('% of Stocks Above 200-Day MA', fontsize=12, fontweight='bold')
    ax.set_title('Market Breadth Analysis: Percentage of Stocks Above 200-Day Moving Average', 
                 fontsize=14, fontweight='bold', pad=20)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # Set y-axis limits
    ax.set_ylim(0, 100)
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha='right')
    
    # Tight layout
    plt.tight_layout()
    
    # Save the plot
    output_path = Path(csv_path).parent / f"{Path(csv_path).stem}_plot.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✅ Plot saved to: {output_path}")
    
    # Show the plot
    plt.show()
    
    # Print some statistics
    print("\n" + "="*60)
    print("MARKET BREADTH STATISTICS")
    print("="*60)
    print(f"\nPeriod: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Data points: {len(df)}")
    
    print(f"\nTop 100 Stocks:")
    print(f"  Average: {df['top_100_pct'].mean():.1f}%")
    print(f"  Median:  {df['top_100_pct'].median():.1f}%")
    print(f"  Min:     {df['top_100_pct'].min():.1f}% ({df[df['top_100_pct'] == df['top_100_pct'].min()]['date'].values[0]})")
    print(f"  Max:     {df['top_100_pct'].max():.1f}% ({df[df['top_100_pct'] == df['top_100_pct'].max()]['date'].values[0]})")
    
    print(f"\nTop 1000 Stocks:")
    print(f"  Average: {df['top_1000_pct'].mean():.1f}%")
    print(f"  Median:  {df['top_1000_pct'].median():.1f}%")
    print(f"  Min:     {df['top_1000_pct'].min():.1f}% ({df[df['top_1000_pct'] == df['top_1000_pct'].min()]['date'].values[0]})")
    print(f"  Max:     {df['top_1000_pct'].max():.1f}% ({df[df['top_1000_pct'] == df['top_1000_pct'].max()]['date'].values[0]})")
    
    # Current reading (last date)
    last_row = df.iloc[-1]
    print(f"\nCurrent Reading ({last_row['date'].date()}):")
    print(f"  Top 100:  {last_row['top_100_pct']:.1f}%")
    print(f"  Top 1000: {last_row['top_1000_pct']:.1f}%")
    print("="*60)

if __name__ == "__main__":
    # Find the most recent market breadth CSV
    reports_dir = Path(__file__).parent / "outputs" / "reports"
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Find most recent market_breadth CSV
        csv_files = list(reports_dir.glob("market_breadth_*.csv"))
        if not csv_files:
            print("Error: No market breadth CSV files found!")
            sys.exit(1)
        
        csv_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        print(f"Using most recent file: {csv_path.name}")
    
    plot_market_breadth(csv_path)
