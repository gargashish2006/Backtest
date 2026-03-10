#!/usr/bin/env python
"""
Display validation results in matrix format
Rows: Lookback periods
Columns: Holding periods
"""

import pandas as pd
from pathlib import Path

def print_matrix(data, title, decimals=2):
    """Print data in clean matrix format"""
    print(f"\n{title}")
    print("┌" + "─" * 60 + "┐")
    
    pivot_str = data.round(decimals).to_string()
    for line in pivot_str.split('\n'):
        print("│ " + line.ljust(58) + " │")
    
    print("└" + "─" * 60 + "┘")

def show_consolidated_tables():
    base_path = Path(__file__).parent.parent
    reports_path = base_path / 'analysis' / 'outputs' / 'reports'
    
    # Get latest files
    summary_files = sorted(reports_path.glob('industry_validation_summary_*.csv'))
    spread_files = sorted(reports_path.glob('industry_validation_spread_*.csv'))
    
    if not summary_files:
        print("No summary files found")
        return
    
    df = pd.read_csv(summary_files[-1])
    
    # Format lookback labels
    def format_lookback(q):
        return f"{int(q)}Q"
    
    # Display matrices for each method
    for method in ['Pure Contrarian', 'Trend Filtered (50%)', 'Trend Filtered (30%)']:
        print("\n" + "╔" + "═" * 78 + "╗")
        print("║" + f" {method.upper()}".ljust(78) + "║")
        print("╚" + "═" * 78 + "╝")
        
        for group in ['Bottom 10', 'Top 10']:
            subset = df[(df['method'] == method) & (df['group'] == group)]
            
            if len(subset) == 0:
                continue
            
            # Returns matrix
            pivot = subset.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='avg_return',
                aggfunc='first'
            )
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [format_lookback(q) for q in pivot.index]
            print_matrix(pivot, f"{group} - Avg Returns (%)", 2)
            
            # Win rates matrix
            pivot = subset.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='win_rate',
                aggfunc='first'
            )
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [format_lookback(q) for q in pivot.index]
            print_matrix(pivot, f"{group} - Win Rate (%)", 1)
            
            # Sharpe matrix
            pivot = subset.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='sharpe',
                aggfunc='first'
            )
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [format_lookback(q) for q in pivot.index]
            print_matrix(pivot, f"{group} - Sharpe Ratio", 3)
    
    # Spread Analysis
    if spread_files:
        spread_df = pd.read_csv(spread_files[-1])
        
        print("\n" + "╔" + "═" * 78 + "╗")
        print("║" + " SPREAD ANALYSIS (BOTTOM 10 - TOP 10)".ljust(78) + "║")
        print("╚" + "═" * 78 + "╝")
        
        for method_code, method_label in [
            ('pure', 'Pure Contrarian'), 
            ('filtered', 'Trend Filtered (50%)'),
            ('filtered_30', 'Trend Filtered (30%)')
        ]:
            method_data = spread_df[spread_df['method'] == method_code]
            
            if len(method_data) == 0:
                continue
            
            print(f"\n┌─ {method_label} " + "─" * (60 - len(method_label)) + "┐")
            
            # Average spread
            pivot = method_data.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='Avg Spread',
                aggfunc='first'
            )
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [format_lookback(q) for q in pivot.index]
            print_matrix(pivot, "Avg Spread (%)", 2)
            
            # Spread win rate
            pivot = method_data.pivot_table(
                index='lookback_quarters',
                columns='holding_days',
                values='Win Rate %',
                aggfunc='first'
            )
            pivot.columns = [f"{int(c)}d" for c in pivot.columns]
            pivot.index = [format_lookback(q) for q in pivot.index]
            print_matrix(pivot, "Spread Win Rate (%)", 1)
            
            print("└" + "─" * 60 + "┘")

if __name__ == "__main__":
    show_consolidated_tables()
