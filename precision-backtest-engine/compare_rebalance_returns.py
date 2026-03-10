
import pandas as pd
from pathlib import Path

def compare_rebalances():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    var_path = repo_root / "outputs/lookback_8q_nav.csv"
    
    if not champ_path.exists() or not var_path.exists():
        print("Error: NAV files not found. Please run simulations first.")
        return

    champ_df = pd.read_csv(champ_path)
    var_df = pd.read_csv(var_path)
    
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    var_df['date'] = pd.to_datetime(var_df['date'])
    
    # Merge on date
    merged = pd.merge(champ_df, var_df, on='date', suffixes=('_champ', '_8q'))
    
    # Define Rebalance Schedule (Standard)
    # We want to capture the value at each rebalance date to calculate period return
    rebalance_schedule = []
    start_year = merged['date'].dt.year.min()
    end_year = merged['date'].dt.year.max()
    
    for year in range(start_year, end_year + 1):
        for month in [2, 5, 8, 11]:
            # Target date 15th
            target = pd.Timestamp(year=year, month=month, day=15)
            # Find closest available date <= target
            available = merged[merged['date'] <= target]
            if not available.empty:
                actual = available['date'].iloc[-1]
                # Avoid duplicates and ensure strictly increasing
                if not rebalance_schedule or actual > rebalance_schedule[-1]:
                     rebalance_schedule.append(actual)
    
    # Calculate Period Returns
    results = []
    
    prev_date = rebalance_schedule[0]
    
    # Get initial NAVs
    row_prev = merged[merged['date'] == prev_date].iloc[0]
    prev_nav_champ = row_prev['nav_champ']
    prev_nav_8q = row_prev['nav_8q']
    
    for curr_date in rebalance_schedule[1:]:
        row_curr = merged[merged['date'] == curr_date].iloc[0]
        
        curr_nav_champ = row_curr['nav_champ']
        curr_nav_8q = row_curr['nav_8q']
        
        ret_champ = (curr_nav_champ / prev_nav_champ) - 1
        ret_8q = (curr_nav_8q / prev_nav_8q) - 1
        diff = ret_champ - ret_8q
        
        results.append({
            "Period End": curr_date.strftime('%Y-%m-%d'),
            "Champion (1Y)": ret_champ,
            "Variation (2Y)": ret_8q,
            "Diff (Champ - Var)": diff
        })
        
        prev_date = curr_date
        prev_nav_champ = curr_nav_champ
        prev_nav_8q = curr_nav_8q
        
    # Create DataFrame
    res_df = pd.DataFrame(results)
    
    # Print Table
    print("\n" + "="*80)
    print(f"{'Period End':<15} | {'Champ (1Y)':>12} | {'Var (2Y)':>12} | {'Diff':>12}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['Period End']:<15} | {row['Champion (1Y)']:.2%}       | {row['Variation (2Y)']:.2%}       | {row['Diff (Champ - Var)']:.2%}")
        
    print("="*80)
    
    # Summary Win/Loss
    wins = (res_df['Diff (Champ - Var)'] > 0).sum()
    total = len(res_df)
    print(f"\nChampion Outperformed in {wins}/{total} periods ({wins/total:.1%})")
    
    # Save to CSV
    out_path = repo_root / "outputs/rebalance_comparison_8q.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved detailed comparison to {out_path}")

if __name__ == "__main__":
    compare_rebalances()
