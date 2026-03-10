import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_performance(strat_csv, bench_csv, output_path, title_label="Strategy vs Benchmark"):
    # 1. Load Data
    strat_df = pd.read_csv(strat_csv) if isinstance(strat_csv, (str, Path)) else strat_csv
    
    if isinstance(bench_csv, (str, Path)):
        if str(bench_csv).endswith('.parquet'):
            bench_df = pd.read_parquet(bench_csv)
        else:
            bench_df = pd.read_csv(bench_csv)
    else:
        bench_df = bench_csv
    
    strat_df['date'] = pd.to_datetime(strat_df['date'])
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    
    # 2. Alignment
    start_date = strat_df['date'].min()
    end_date = strat_df['date'].max()
    bench_df = bench_df[(bench_df['date'] >= start_date) & (bench_df['date'] <= end_date)]
    
    merged = pd.merge(strat_df[['date', 'nav']], bench_df[['date', 'index_value']], on='date')
    merged = merged.sort_values('date')
    
    merged['strat_indexed'] = (merged['nav'] / merged['nav'].iloc[0]) * 100
    merged['bench_indexed'] = (merged['index_value'] / merged['index_value'].iloc[0]) * 100
    
    # 3. Plot
    plt.figure(figsize=(10, 5))
    plt.plot(merged['date'], merged['strat_indexed'], label=title_label, color='blue', linewidth=2)
    plt.plot(merged['date'], merged['bench_indexed'], label='Benchmark Top 1000', color='gray', linestyle='--')
    
    plt.title(f"{title_label}\n({start_date.date()} to {end_date.date()})", fontsize=12)
    plt.ylabel("Indexed NAV (100 Base)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig(output_path)
    print(f"Plot saved to: {output_path}")

if __name__ == "__main__":
    from pathlib import Path
    base_dir = Path(__file__).parent.parent
    
    # Industry Momentum RSNP
    rsnp_nav = base_dir / "outputs/industry_momentum_rsnp_nav.csv"
    bench_p = base_dir / "benchmarks/Benchmark_1000_equalWeight.parquet"
    out_p = base_dir / "outputs/industry_momentum_rsnp_vs_benchmark.png"
    
    if rsnp_nav.exists():
        plot_performance(rsnp_nav, bench_p, out_p, "Industry Momentum RSNP")
