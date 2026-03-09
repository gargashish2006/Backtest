import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def find_gr_infra():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    
    for isin, name in dh.isin_to_name.items():
        if "G R" in name or "Infra" in name:
            print(f"{isin}: {name} ({dh.isin_to_industry.get(isin)})")
            
if __name__ == "__main__":
    find_gr_infra()
