
import pandas as pd
from pathlib import Path

def compare_rebalances():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    strat_path = repo_root / "outputs/top100_decrease_nav.csv"
    bench_path = repo_root / "outputs/top100_benchmark_nav.csv"
    
    if not strat_path.exists() or not bench_path.exists():
        print("Error: NAV files not found. Please run simulations first.")
        return

    strat_df = pd.read_csv(strat_path)
    bench_df = pd.read_csv(bench_path)
    
    strat_df['date'] = pd.to_datetime(strat_df['date'])
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    
    merged = pd.merge(strat_df, bench_df, on='date', suffixes=('_strat', '_bench'))
    
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
    prev_nav_s = row_prev['nav_strat']
    prev_nav_b = row_prev['nav_bench']
    
    for curr_date in rebalance_schedule[1:]:
        row_curr = merged[merged['date'] == curr_date].iloc[0]
        
        curr_nav_s = row_curr['nav_strat']
        curr_nav_b = row_curr['nav_bench']
        
        ret_s = (curr_nav_s / prev_nav_s) - 1
        ret_b = (curr_nav_b / prev_nav_b) - 1
        diff = ret_s - ret_b
        
        results.append({
            "Period End": curr_date.strftime('%Y-%m-%d'),
            "Decrease Strat": ret_s,
            "Benchmark (100)": ret_b,
            "Diff": diff
        })
        
        prev_date = curr_date
        prev_nav_s = curr_nav_s
        prev_nav_b = curr_nav_b
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'Period End':<15} | {'Decrease Strat':>15} | {'Benchmark (100)':>15} | {'Diff':>12}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['Period End']:<15} | {row['Decrease Strat']:.2%}       | {row['Benchmark (100)']:.2%}       | {row['Diff']:.2%}")
        
    print("="*80)
    
    wins = (res_df['Diff'] > 0).sum()
    total = len(res_df)
    print(f"\nStrategy Outperformed Benchmark in {wins}/{total} periods ({wins/total:.1%})")
    
    out_path = repo_root / "outputs/rebalance_comparison_top100_decrease.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved comparison to {out_path}")

if __name__ == "__main__":
    compare_rebalances()
