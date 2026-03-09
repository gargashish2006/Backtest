import pandas as pd
from pathlib import Path

def convert_csv_to_excel():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    csv_path = repo_root / "feb_2026_industry_signals.csv"
    excel_path = repo_root / "outputs/feb_2026_industry_signals.xlsx"
    
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    
    # Optional: Format the columns for better Excel display
    df.columns = [col.replace('_', ' ').title() for col in df.columns]
    
    try:
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"Successfully converted to Excel: {excel_path}")
    except ImportError:
        print("Error: openpyxl is not installed. Attempting to install...")
        # Since I can run commands, I could install it, but let's try to see if it works first.
        # Alternatively, use xlsxwriter if available.
        raise

if __name__ == "__main__":
    convert_csv_to_excel()
