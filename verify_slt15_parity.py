import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.slt15_strategy import SLT15Strategy

def verify_parity():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    date = pd.Timestamp("2026-02-05")
    
    # 1. Class Output
    strategy = SLT15Strategy(dh)
    class_selection = strategy.calculate_selection(date)
    
    # 2. Results from production script (manual check or automated)
    # We know the list from previous command status:
    # Cartrade Tech, FSN E-Commerce, Eternal (E-Retail)
    # Fine Organic, Jubilant Ingrev, Archean (Specialty Chem)
    # Campus, Relaxo, Bata (Footwear)
    # LIC, HDFC, ICICI (Life Ins)
    # Greenpanel, Century, Greenlam (Plywood)
    
    print("\nSLT15Strategy Class Selection for Feb 2026:")
    for isin, wt in class_selection.items():
        name = dh.isin_to_name.get(isin, isin)
        ind = dh.isin_to_industry.get(isin)
        print(f"[{ind}] {name}: {wt:.4f}")
        
    print(f"\nTotal Stocks selected: {len(class_selection)}")
    if len(class_selection) == 15:
        print("\nSelection count matches (15).")
    else:
        print(f"\nWARNING: Selection count mismatch! Found {len(class_selection)} stocks.")

if __name__ == "__main__":
    verify_parity()
