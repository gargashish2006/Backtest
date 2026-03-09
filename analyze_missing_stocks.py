import pandas as pd
import ast
from pathlib import Path

def analyze_missing():
    root = Path(__file__).parent
    base_path = root / "outputs/champion_full_nav.csv"
    var_path = root / "outputs/champion_2yr_nav.csv"
    
    if not base_path.exists() or not var_path.exists():
        print("Missing nav files.")
        return
        
    base_df = pd.read_csv(base_path)
    var_df = pd.read_csv(var_path)
    
    # Load metadata for names
    industry_path = root / "database/industry_info.csv"
    name_map = {}
    if industry_path.exists():
        ind_df = pd.read_csv(industry_path)
        name_map = dict(zip(ind_df['isin'], ind_df['company_name']))
        
    # Get first dates (for history checks)
    price_df = pd.read_parquet(root / "database/price_data.parquet")
    first_dates = price_df.groupby('isin')['date'].min().to_dict()
    del price_df # Free memory
    
    # Analyze rebalance dates (whenever portfolio changes)
    def get_portfolio_map(df):
        df['date'] = pd.to_datetime(df['date'])
        df['pos_list'] = df['positions'].apply(ast.literal_eval)
        # Filter for rebalance points (first day where portfolio differs from previous)
        rebalance_pts = []
        prev = set()
        for idx, row in df.iterrows():
            curr = set(row['pos_list'])
            if curr != prev and len(curr) > 0:
                rebalance_pts.append(row)
            prev = curr
        return rebalance_pts

    base_pts = get_portfolio_map(base_df)
    var_pts = get_portfolio_map(var_df)
    
    var_dates_map = {p['date']: set(p['pos_list']) for p in var_pts}
    
    print(f"{'Date':<12} | {'Missing Stock':<30} | {'Listed On':<12}")
    print("-" * 60)
    
    missing_counts = {}
    
    for pt in base_pts:
        d = pt['date']
        base_pos = set(pt['pos_list'])
        var_pos = var_dates_map.get(d, set())
        
        missing = base_pos - var_pos
        for isin in missing:
            name = name_map.get(isin, isin)
            first_d = pd.to_datetime(first_dates.get(isin))
            diff_days = (d - first_d).days
            
            # Category: Direct (History) or Indirect (Industry Filter)
            if diff_days < 730:
                reason = "DIRECT (Age < 2yr)"
            else:
                reason = "INDIRECT (Industry Failed)"
                
            if name == "SBI Life Insurance" or name == "SBI Life Insuran":
                print(f"{str(d.date()):<12} | {name:<20} | {first_d.strftime('%Y-%m-%d'):<12} | {reason}")
            
            missing_counts[name] = missing_counts.get(name, 0) + 1

    print("\nSummary: Most Critical Stocks Filtered Out (Top 10)")
    sorted_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)
    for name, count in sorted_missing[:10]:
        print(f" - {name}: Held in {count} rebalance periods in Baseline")

if __name__ == "__main__":
    analyze_missing()
