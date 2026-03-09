import pandas as pd
import ast
from pathlib import Path

def analyze_jk_paper_discrepancy():
    root = Path(__file__).parent
    base_nav_path = root / "outputs/champion_full_nav.csv"
    var_nav_path = root / "outputs/champion_2yr_nav.csv" # This now contains the 1.5yr run
    
    isin = "INE789E01012" # JK Paper
    
    base_df = pd.read_csv(base_nav_path)
    var_df = pd.read_csv(var_nav_path)
    
    base_df['date'] = pd.to_datetime(base_df['date'])
    var_df['date'] = pd.to_datetime(var_df['date'])
    
    base_df['positions'] = base_df['positions'].apply(ast.literal_eval)
    var_df['positions'] = var_df['positions'].apply(ast.literal_eval)
    
    # Target date: Aug 16, 2018 (The rebalance where JK Paper entered baseline)
    target_date = pd.Timestamp("2018-08-16")
    
    base_row = base_df[base_df['date'] == target_date]
    var_row = var_df[var_df['date'] == target_date]
    
    if base_row.empty or var_row.empty:
        # Try nearest date
        target_date = pd.Timestamp("2018-08-14") # The day before rebalance usually shows selection
        base_row = base_df[base_df['date'] >= target_date].iloc[0]
        var_row = var_df[var_df['date'] >= target_date].iloc[0]
        target_date = base_row['date']
    else:
        base_row = base_row.iloc[0]
        var_row = var_row.iloc[0]

    base_pos = set(base_row['positions'])
    var_pos = set(var_row['positions'])
    
    print(f"--- Analysis for Date: {target_date.date()} ---")
    print(f"JK Paper in Baseline: {isin in base_pos}")
    print(f"JK Paper in 1.5yr Var: {isin in var_pos}")
    
    # Why the difference? Let's look at the universe size and selection
    # In the 1.5yr variation, some stocks were REMOVED from the starting universe.
    # This changes the "Industry Breadth" (RSNP) calculation for EVERY industry.
    
    # Get Industry for JK Paper
    industry_path = root / "database/industry_info.csv"
    ind_df = pd.read_csv(industry_path)
    jk_industry = ind_df[ind_df['isin'] == isin]['industry'].iloc[0]
    print(f"JK Paper Industry: {jk_industry}")
    
    # Stocks in this industry
    industry_stocks = ind_df[ind_df['industry'] == jk_industry]['isin'].tolist()
    
    # Check eligibility of these stocks on 2018-08-16
    price_df = pd.read_parquet(root / "database/price_data.parquet")
    first_dates = price_df.groupby('isin')['date'].min().to_dict()
    
    print(f"\nEvaluating industry '{jk_industry}' eligibility (1.5yr filter):")
    cutoff = target_date - pd.Timedelta(days=int(1.5 * 365.25))
    
    total_in_ind = 0
    eligible_in_ind = 0
    for s_isin in industry_stocks:
        first_d = pd.to_datetime(first_dates.get(s_isin))
        if first_d <= target_date: # Exists
            total_in_ind += 1
            if first_d <= cutoff: # Eligible
                eligible_in_ind += 1
            else:
                print(f" - {s_isin} (New) EXCLUDED. Listed: {first_d.date()}")

    print(f"Total existing in Ind: {total_in_ind}")
    print(f"Eligible for RSNP in Var: {eligible_in_ind}")
    
    if eligible_in_ind < 3: # min_industry_size is 3
        print(f"\n>>> THE CULPRIT: Industry '{jk_industry}' felt below the minimum size (3) because young peer stocks were filtered out!")
        print("Thus, even if JK Paper was 10 years old, it was disqualified because its industry no longer had enough 'eligible' members to calculate a valid signal.")

if __name__ == "__main__":
    analyze_jk_paper_discrepancy()
