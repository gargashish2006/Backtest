
import pandas as pd
from pathlib import Path

def compare_champion_vs_frictionless():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    bench_path = repo_root / "outputs/top1000_frictionless_nav.csv"
    
    if not champ_path.exists() or not bench_path.exists():
        print("Error: NAV files not found. Please run simulations first.")
        return

    champ_df = pd.read_csv(champ_path)
    bench_df = pd.read_csv(bench_path)
    
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    
    merged = pd.merge(champ_df, bench_df, on='date', suffixes=('_champ', '_bench'))
    
    # Rebalance Schedule (Quarterly: Feb, May, Aug, Nov)
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
                     
    # Calculate Period Returns
    results = []
    if not rebalance_schedule:
        print("Error: No common dates found.")
        return
        
    prev_date = rebalance_schedule[0]
    
    # Initial
    row_prev = merged[merged['date'] == prev_date].iloc[0]
    prev_nav_c = row_prev['nav_champ']
    prev_nav_b = row_prev['nav_bench']
    
    for curr_date in rebalance_schedule[1:]:
        row_curr = merged[merged['date'] == curr_date].iloc[0]
        
        curr_nav_c = row_curr['nav_champ']
        curr_nav_b = row_curr['nav_bench']
        
        ret_c = (curr_nav_c / prev_nav_c) - 1
        ret_b = (curr_nav_b / prev_nav_b) - 1
        diff = ret_c - ret_b
        
        results.append({
            "Period End": curr_date.strftime('%Y-%m-%d'),
            "Champion (Net)": ret_c,
            "Benchmark (Gross)": ret_b,
            "Alpha": diff
        })
        
        prev_date = curr_date
        prev_nav_c = curr_nav_c
        prev_nav_b = curr_nav_b
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print("CHAMPION (NET OF FEES/TAX) vs FRICTIONLESS TOP 1000 BENCHMARK")
    print("="*80)
    print(f"{'Period End':<15} | {'Champion (Net)':>15} | {'Bench (Gross)':>15} | {'Alpha':>10}")
    print("-" * 80)
    
    for _, row in res_df.iterrows():
        print(f"{row['Period End']:<15} | {row['Champion (Net)']:.2%}       | {row['Benchmark (Gross)']:.2%}       | {row['Alpha']:.2%}")
        
    print("="*80)
    
    wins = (res_df['Alpha'] > 0).sum()
    total = len(res_df)
    print(f"\nChampion Outperformed in {wins}/{total} periods ({wins/total:.1%})")
    
    # Calculate Total CAGR/DD for Context
    start_val_c = champ_df['nav'].iloc[0]
    end_val_c = champ_df['nav'].iloc[-1]
    msg_c = (end_val_c / start_val_c) ** (365 / (merged['date'].iloc[-1] - merged['date'].iloc[0]).days) - 1
    
    start_val_b = bench_df['nav'].iloc[0]
    end_val_b = bench_df['nav'].iloc[-1]
    msg_b = (end_val_b / start_val_b) ** (365 / (merged['date'].iloc[-1] - merged['date'].iloc[0]).days) - 1
    
    print("-" * 50)
    print(f"Champion CAGR (Net): {msg_c:.2%}")
    print(f"Benchmark CAGR (Gross): {msg_b:.2%}")
    print(f"Alpha (CAGR): {msg_c - msg_b:.2%}")
    print("-" * 50)

    out_path = repo_root / "outputs/rebalance_comparison_frictionless.csv"
    res_df.to_csv(out_path, index=False)
    
    # Plot
    import matplotlib.pyplot as plt
    champ_series = champ_df.set_index('date')['nav']
    bench_series = bench_df.set_index('date')['nav']
    
    plt.figure(figsize=(12, 6))
    plt.plot(champ_series, label=f'Champion (Net) - CAGR {msg_c:.1%}', linewidth=2)
    plt.plot(bench_series, label=f'Benchmark (Gross) - CAGR {msg_b:.1%}', alpha=0.7, linestyle='--')
    plt.title('Champion Strategy (Net) vs Frictionless Top 1000 Benchmark (Gross)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(repo_root / "outputs/champion_vs_frictionless_benchmark.png")
    print(f"Comparison chart saved to: {repo_root / 'outputs' / 'champion_vs_frictionless_benchmark.png'}")

if __name__ == "__main__":
    compare_champion_vs_frictionless()
