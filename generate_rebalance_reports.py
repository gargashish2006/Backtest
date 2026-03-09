import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def generate_target_portfolios():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy (50/50/0.40/Limit:3)
    strategy = ContrarianBreadthStrategy(dh, 
                                        max_per_industry=3, 
                                        industry_group_top_pct=0.50, 
                                        industry_decrease_min_pct=0.50,
                                        rsnp_threshold=0.40)
    
    # 3. Define requested dates
    # We need to find the actual trading dates near the 15th of the month
    all_trading_dates = dh.get_all_dates()
    target_months = [('2025-08-15', 'Aug 2025'), ('2025-11-15', 'Nov 2025'), ('2026-02-15', 'Feb 2026')]
    
    isin_to_name = dh.isin_to_name
    
    for date_str, label in target_months:
        d = pd.Timestamp(date_str)
        # Find the latest trading date on or before the target
        valid_dates = [dt for dt in all_trading_dates if dt <= d]
        if not valid_dates: continue
        rebalance_date = max(valid_dates)
        
        print(f"\n{'='*60}")
        print(f"STRATEGY PORTFOLIO: {label} (As of {rebalance_date.date()})")
        print(f"{'='*60}")
        
        selection = strategy.calculate_selection(rebalance_date)
        
        if not selection:
            print("No stocks qualified for this period.")
            continue
            
        # Create a display dataframe
        display_data = []
        for isin, weight in selection.items():
            name = isin_to_name.get(isin, "Unknown")
            industry = dh.isin_to_industry.get(isin, "Unknown")
            group = dh.isin_to_group.get(isin, "Unknown")
            display_data.append({
                'ISIN': isin,
                'Name': name,
                'Industry': industry,
                'Group': group,
                'Weight': f"{weight*100:.2f}%"
            })
            
        df = pd.DataFrame(display_data)
        # Sort by Industry then Name
        df = df.sort_values(['Industry', 'Name'])
        print(df.to_string(index=False))
        print(f"\nTotal Components: {len(df)}")

if __name__ == "__main__":
    generate_target_portfolios()
