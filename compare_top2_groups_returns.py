
import pandas as pd
from pathlib import Path

def compare_rebalances():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    var_path = repo_root / "outputs/top2_groups_nav.csv"
    
    if not champ_path.exists() or not var_path.exists():
        print("Error: NAV files not found. Please run simulations first.")
        return

    champ_df = pd.read_csv(champ_path)
    var_df = pd.read_csv(var_path)
    
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    var_df['date'] = pd.to_datetime(var_df['date'])
    
    merged = pd.merge(champ_df, var_df, on='date', suffixes=('_champ', '_top2'))
    
    # Rebalance Schedule
    rebalance_schedule = []
    start_year = merged['date'].dt.year.min()
    end_year = merged['date'].dt.year.max()
    
    for year in range(start_year, end_year + 1):
        for month in [2, 5, 8, 11]:
            target = pd.Timestamp(year=year, month=month, day=15)
            available = merged[merged['date'] <= target]
            if not available.empty:
                actual = available['date'].iloc[-1]
                if not rebalance_schedule or actual > rebalance_schedule[-1]:
                     rebalance_schedule.append(actual)
    
    results = []
    prev_date = rebalance_schedule[0]
    
    # Initial
    row_prev = merged[merged['date'] == prev_date].iloc[0]
    prev_nav_champ = row_prev['nav_champ']
    prev_nav_var = row_prev['nav_top2']
    
    for curr_date in rebalance_schedule[1:]:
        row_curr = merged[merged['date'] == curr_date].iloc[0]
        
        curr_nav_champ = row_curr['nav_champ']
        curr_nav_var = row_curr['nav_top2']
        
        ret_champ = (curr_nav_champ / prev_nav_champ) - 1
        ret_var = (curr_nav_var / prev_nav_var) - 1
        diff = ret_champ - ret_var
        
        results.append({
            "Period End": curr_date.strftime('%Y-%m-%d'),
            "Champion (1Y)": ret_champ,
            "Top 2 Groups": ret_var,
            "Diff (Champ - Var)": diff
        })
        
        prev_date = curr_date
        prev_nav_champ = curr_nav_champ
        prev_nav_var = curr_nav_var
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'Period End':<15} | {'Champ (1Y)':>12} | {'Top 2 G':>12} | {'Diff':>12}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['Period End']:<15} | {row['Champion (1Y)']:.2%}       | {row['Top 2 Groups']:.2%}       | {row['Diff (Champ - Var)']:.2%}")
        
    print("="*80)
    
    wins = (res_df['Diff (Champ - Var)'] > 0).sum()
    total = len(res_df)
    print(f"\nChampion Outperformed in {wins}/{total} periods ({wins/total:.1%})")
    
    out_path = repo_root / "outputs/rebalance_comparison_top2.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved comparison to {out_path}")

if __name__ == "__main__":
    compare_rebalances()
