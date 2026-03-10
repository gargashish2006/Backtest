
import pandas as pd
from pathlib import Path

def check_counts():
    repo_root = Path(__file__).parent
    excel_path = repo_root / "outputs/historic_sequential_selections.xlsx"
    
    if not excel_path.exists():
        print("Excel file not found.")
        return

    print(f"Verifying Industry Sequential Threshold >= 25% in {excel_path.name}...\n")
    
    xl = pd.ExcelFile(excel_path)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        count = len(df)
        min_score = df['Sequential Ind Score'].min() if not df.empty and 'Sequential Ind Score' in df.columns else 0
        print(f"{sheet:<10}: Found {count} industries. Min Ind Score: {min_score:.1%}")

if __name__ == "__main__":
    check_counts()
