#!/usr/bin/env python
"""
Display validation results in table format
Rows: Lookback periods
Columns: Holding periods
"""

import pandas as pd
from pathlib import Path

def display_results():
    # Find latest files
    base_path = Path(__file__).parent.parent
    reports_path = base_path / 'analysis' / 'outputs' / 'reports'
    
    # Get latest summary file
    summary_files = sorted(reports_path.glob('industry_validation_summary_*.csv'))
    if not summary_files:
        print("No summary files found")
        return
    
    summary_file = summary_files[-1]
    print(f"Reading: {summary_file.name}\n")
    
    df = pd.read_csv(summary_file)
    
    # Display for Bottom 10 Industries (most important)
    print("="*100)
    print("BOTTOM 10 INDUSTRIES - AVERAGE RETURNS (%)")
    print("="*100)
    
    for method in df['method'].unique():
        method_data = df[(df['method'] == method) & (df['group'] == 'Bottom 10')]
        
        print(f"\n{method}:")
        print("-" * 70)
        
        # Create pivot table
        pivot = method_data.pivot_table(
            index='lookback_quarters',
            columns='holding_days',
            values='avg_return',
            aggfunc='first'
        )
        
        # Format column names
        pivot.columns = [f"{int(c)}d" for c in pivot.columns]
        pivot.index.name = 'Lookback'
        
        # Add lookback in months
        pivot.index = [f"{int(q)}Q ({int(q)*3}m)" for q in pivot.index]
        
        print(pivot.round(2).to_string())
    
    # Display Win Rates
    print("\n\n" + "="*100)
    print("BOTTOM 10 INDUSTRIES - WIN RATES (%)")
    print("="*100)
    
    for method in df['method'].unique():
        method_data = df[(df['method'] == method) & (df['group'] == 'Bottom 10')]
        
        print(f"\n{method}:")
        print("-" * 70)
        
        pivot = method_data.pivot_table(
            index='lookback_quarters',
            columns='holding_days',
            values='win_rate',
            aggfunc='first'
        )
        
        pivot.columns = [f"{int(c)}d" for c in pivot.columns]
        pivot.index = [f"{int(q)}Q ({int(q)*3}m)" for q in pivot.index]
        
        print(pivot.round(1).to_string())
    
    # Display Sharpe Ratios
    print("\n\n" + "="*100)
    print("BOTTOM 10 INDUSTRIES - SHARPE RATIOS")
    print("="*100)
    
    for method in df['method'].unique():
        method_data = df[(df['method'] == method) & (df['group'] == 'Bottom 10')]
        
        print(f"\n{method}:")
        print("-" * 70)
        
        pivot = method_data.pivot_table(
            index='lookback_quarters',
            columns='holding_days',
            values='sharpe',
            aggfunc='first'
        )
        
        pivot.columns = [f"{int(c)}d" for c in pivot.columns]
        pivot.index = [f"{int(q)}Q ({int(q)*3}m)" for q in pivot.index]
        
        print(pivot.round(3).to_string())
    
    # Display SPREAD Analysis
    print("\n\n" + "="*100)
    print("SPREAD (Bottom 10 - Top 10) - AVERAGE SPREAD (%)")
    print("="*100)
    
    # Read spread file
    spread_files = sorted(reports_path.glob('industry_validation_spread_*.csv'))
    if spread_files:
        spread_df = pd.read_csv(spread_files[-1])
        
        for method in ['filtered', 'pure']:
            method_label = 'Trend Filtered' if method == 'filtered' else 'Pure Contrarian'
            method_data = spread_df[spread_df['method'] == method]
            
            print(f"\n{method_label}:")
            print("-" * 70)
            
            pivot = method_data.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='Avg Spread',
                aggfunc='first'
            )
            
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [f"{int(q)}Q ({int(q)*3}m)" for q in pivot.index]
            
            print(pivot.round(2).to_string())
        
        # Spread Win Rate
        print("\n\n" + "="*100)
        print("SPREAD (Bottom 10 - Top 10) - WIN RATE (% times spread > 0)")
        print("="*100)
        
        for method in ['filtered', 'pure']:
            method_label = 'Trend Filtered' if method == 'filtered' else 'Pure Contrarian'
            method_data = spread_df[spread_df['method'] == method]
            
            print(f"\n{method_label}:")
            print("-" * 70)
            
            pivot = method_data.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='Win Rate %',
                aggfunc='first'
            )
            
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [f"{int(q)}Q ({int(q)*3}m)" for q in pivot.index]
            
            print(pivot.round(1).to_string())

if __name__ == "__main__":
    display_results()
