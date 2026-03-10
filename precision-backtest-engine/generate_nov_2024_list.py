import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def get_nov_2024_rebalance():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Identify valid Nov 2024 rebalance date (closest to 15th)
    all_dates = dh.get_all_dates()
    target = pd.Timestamp("2024-11-15")
    valid_dates = [d for d in all_dates if d <= target]
    reb_date = max(valid_dates)
    
    # 2. Setup 15-stock strategy
    strategy = ContrarianBreadthStrategy(
        data_handler=dh,
        num_stocks=15,
        rsnp_threshold=0.4,
        rsi_threshold=40,
        rsi_exit_threshold=39
    )
    
    # 3. Calculate selection
    selection = strategy.calculate_selection(reb_date)
    
    print(f"\nREBALANCE LIST FOR {reb_date.strftime('%Y-%m-%d')}")
    print("="*60)
    print(f"{'#':<3} | {'ISIN':<12} | {'Company Name':<35}")
    print("-" * 60)
    
    for i, (isin, weight) in enumerate(selection.items(), 1):
        name = dh.isin_to_name.get(isin, "Unknown")
        print(f"{i:<3} | {isin:<12} | {name:<35}")
    print("="*60)

if __name__ == "__main__":
    get_nov_2024_rebalance()
