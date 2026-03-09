import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def find_specific_isin():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    
    isin = "INE144H01011"
    print(f"Name: {dh.isin_to_name.get(isin)}")
    print(f"Industry: {dh.isin_to_industry.get(isin)}")
    print(f"Group: {dh.isin_to_group.get(isin)}")
            
if __name__ == "__main__":
    find_specific_isin()
