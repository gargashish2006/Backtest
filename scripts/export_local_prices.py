import sys
from pathlib import Path
import pandas as pd

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

from data.data_handler import DataHandler

def export_local_prices():
    print("Loading local database...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    
    target_dates = [pd.Timestamp("2026-01-22"), pd.Timestamp("2026-01-23"), pd.Timestamp("2026-01-27")]
    
    # Filter price_df for target dates
    filtered_df = dh.price_df[dh.price_df['date'].isin(target_dates)]
    
    # Select needed columns
    output_df = filtered_df[['date', 'isin', 'close']].copy()
    
    # Export to a temporary csv
    output_path = repo_root / "temp_local_prices_jan23_27.csv"
    output_df.to_csv(output_path, index=False)
    
    print(f"Exported {len(output_df)} local price records to {output_path}")

if __name__ == "__main__":
    export_local_prices()
