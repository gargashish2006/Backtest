#!/usr/bin/env python
"""
Plot Shareholding Concentration Analysis Results
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

def plot_shareholding_concentration(csv_path):
    """Plot shareholding concentration results from CSV file"""
    
    # Read the data
    df = pd.read_csv(csv_path)
    df['quarter_date'] = pd.to_datetime(df['quarter_date'])
    
    # Convert to Lakhs for better readability
    df['avg_in_lakhs'] = df['avg_market_cap_per_shareholder'] / 100000
    df['median_in_lakhs'] = df['median_market_cap_per_shareholder'] / 100000
    
    # Create the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot 1: Average Market Cap per Shareholder
    ax1.plot(df['quarter_date'], df['avg_in_lakhs'], 
            label='Average', 
            linewidth=2.5, 
            marker='o', 
            markersize=6,
            color='#1f77b4',
            alpha=0.8)
    
    ax1.plot(df['quarter_date'], df['median_in_lakhs'], 
            label='Median', 
            linewidth=2, 
            marker='s', 
            markersize=5,
            color='#ff7f0e',
            alpha=0.7)
    
    ax1.set_xlabel('Quarter', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Market Cap per Shareholder (₹ Lakhs)', fontsize=11, fontweight='bold')
    ax1.set_title('Shareholding Concentration Over Time\nAverage Market Cap per Shareholder', 
                 fontsize=13, fontweight='bold', pad=15)
    
    ax1.legend(loc='best', fontsize=10, framealpha=0.9)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # Rotate x-axis labels
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Plot 2: Number of Stocks Analyzed per Quarter
    ax2.bar(df['quarter_date'], df['num_stocks'], 
            color='#2ca02c',
            alpha=0.7,
            edgecolor='black',
            linewidth=0.5)
    
    ax2.set_xlabel('Quarter', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Number of Stocks', fontsize=11, fontweight='bold')
    ax2.set_title('Number of Stocks with Valid Data per Quarter', 
                 fontsize=13, fontweight='bold', pad=15)
    
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='y')
    
    # Rotate x-axis labels
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Tight layout
    plt.tight_layout()
    
    # Save the plot
    output_path = Path(csv_path).parent / f"{Path(csv_path).stem}_plot.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✅ Plot saved to: {output_path}")
    
    # Show the plot
    plt.show()
    
    # Print statistics
    print("\n" + "="*70)
    print("SHAREHOLDING CONCENTRATION STATISTICS")
    print("="*70)
    print(f"\nPeriod: {df['quarter_date'].min().date()} to {df['quarter_date'].max().date()}")
    print(f"Total Quarters: {len(df)}")
    
    print(f"\nAverage Market Cap per Shareholder:")
    print(f"  Mean:   ₹{df['avg_market_cap_per_shareholder'].mean():>12,.2f} ({df['avg_in_lakhs'].mean():.2f} Lakhs)")
    print(f"  Median: ₹{df['avg_market_cap_per_shareholder'].median():>12,.2f} ({df['avg_in_lakhs'].median():.2f} Lakhs)")
    print(f"  Min:    ₹{df['avg_market_cap_per_shareholder'].min():>12,.2f} ({df[df['avg_market_cap_per_shareholder'] == df['avg_market_cap_per_shareholder'].min()]['quarter_date'].values[0]})")
    print(f"  Max:    ₹{df['avg_market_cap_per_shareholder'].max():>12,.2f} ({df[df['avg_market_cap_per_shareholder'] == df['avg_market_cap_per_shareholder'].max()]['quarter_date'].values[0]})")
    
    # Calculate trend
    first_half = df.head(len(df)//2)['avg_market_cap_per_shareholder'].mean()
    second_half = df.tail(len(df)//2)['avg_market_cap_per_shareholder'].mean()
    change_pct = ((second_half - first_half) / first_half) * 100
    
    print(f"\nTrend Analysis:")
    print(f"  First Half Average:  ₹{first_half:,.2f}")
    print(f"  Second Half Average: ₹{second_half:,.2f}")
    print(f"  Change: {change_pct:+.1f}%")
    
    # Latest reading
    latest = df.iloc[-1]
    print(f"\nLatest Quarter ({latest['quarter_date'].date()}):")
    print(f"  Avg Market Cap per Shareholder: ₹{latest['avg_market_cap_per_shareholder']:,.2f}")
    print(f"  Median Market Cap per Shareholder: ₹{latest['median_market_cap_per_shareholder']:,.2f}")
    print(f"  Stocks Analyzed: {latest['num_stocks']}")
    print("="*70)

if __name__ == "__main__":
    # Find the most recent shareholding concentration CSV
    reports_dir = Path(__file__).parent / "outputs" / "reports"
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Find the shareholding concentration CSV
        csv_files = list(reports_dir.glob("shareholding_concentration_*.csv"))
        if not csv_files:
            print("Error: No shareholding concentration CSV files found!")
            sys.exit(1)
        
        csv_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        print(f"Using file: {csv_path.name}")
    
    plot_shareholding_concentration(csv_path)
