
import pandas as pd
from pathlib import Path

def compare_variations():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    q3_path = repo_root / "outputs/lookback_3q_nav.csv"
    q2_path = repo_root / "outputs/lookback_2q_nav.csv"
    
    if not champ_path.exists() or not q3_path.exists() or not q2_path.exists():
        print("Error: NAV files not found. Please run simulations first.")
        return

    champ_df = pd.read_csv(champ_path)
    q3_df = pd.read_csv(q3_path)
    q2_df = pd.read_csv(q2_path)
    
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    q3_df['date'] = pd.to_datetime(q3_df['date'])
    q2_df['date'] = pd.to_datetime(q2_df['date'])
    
    # Merge
    merged = pd.merge(champ_df, q3_df, on='date', suffixes=('_champ', '_3q'))
    merged = pd.merge(merged, q2_df, on='date')
    merged = merged.rename(columns={'nav': 'nav_2q'})
    
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
    prev_nav_3q = row_prev['nav_3q']
    prev_nav_2q = row_prev['nav_2q']
    
    for curr_date in rebalance_schedule[1:]:
        row_curr = merged[merged['date'] == curr_date].iloc[0]
        
        curr_nav_champ = row_curr['nav_champ']
        curr_nav_3q = row_curr['nav_3q']
        curr_nav_2q = row_curr['nav_2q']
        
        ret_champ = (curr_nav_champ / prev_nav_champ) - 1
        ret_3q = (curr_nav_3q / prev_nav_3q) - 1
        ret_2q = (curr_nav_2q / prev_nav_2q) - 1
        
        results.append({
            "Period End": curr_date.strftime('%Y-%m-%d'),
            "Original (1Y)": ret_champ,
            "3Q (9M)": ret_3q,
            "2Q (6M)": ret_2q
        })
        
        prev_date = curr_date
        prev_nav_champ = curr_nav_champ
        prev_nav_3q = curr_nav_3q
        prev_nav_2q = curr_nav_2q
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'Period End':<15} | {'Original (1Y)':>15} | {'3Q (9M)':>15} | {'2Q (6M)':>15}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['Period End']:<15} | {row['Original (1Y)']:.2%}       | {row['3Q (9M)']:.2%}       | {row['2Q (6M)']:.2%}")
        
    print("="*80)
    
    out_path = repo_root / "outputs/rebalance_comparison_lookbacks.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved comparison to {out_path}")

if __name__ == "__main__":
    compare_variations()
