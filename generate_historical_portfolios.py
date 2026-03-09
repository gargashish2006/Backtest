import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def generate_historical_reports():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy
    strategy = ContrarianBreadthStrategy(dh)
    
    # 3. Target Rebalance Dates
    target_months = [
        pd.Timestamp("2018-02-15"),
        pd.Timestamp("2020-08-15"),
        pd.Timestamp("2025-08-15"),
        pd.Timestamp("2025-11-15")
    ]
    
    all_dates = dh.get_all_dates()
    
    for month_date in target_months:
        # Find exact rebalance date in data
        reb_date = max([d for d in all_dates if d <= month_date])
        print(f"\n{'='*60}")
        print(f"REBALANCE REPORT: {reb_date.strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        
        # Generate Selection
        selection = strategy.calculate_selection(reb_date)
        
        if not selection:
            print("No stocks selected for this period.")
            continue
            
        # Display Details
        report_data = []
        for isin, weight in selection.items():
            name = dh.isin_to_name.get(isin, "Unknown")
            ind = dh.isin_to_industry.get(isin, "Unknown")
            grp = dh.isin_to_group.get(isin, "Unknown")
            report_data.append({
                'ISIN': isin,
                'Name': name,
                'Industry': ind,
                'Group': grp,
                'Weight': f"{weight*100:.2f}%"
            })
            
        df = pd.DataFrame(report_data)
        print(df.to_string(index=False))
        print(f"Total Stocks: {len(df)}")

if __name__ == "__main__":
    generate_historical_reports()
