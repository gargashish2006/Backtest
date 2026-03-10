import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from utils.analytics import calculate_metrics

def compare_champion_vs_benchmark():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    
    # 1. Load Strategy NAV (Final Champion)
    strat_nav_path = base_path / "outputs/final_champion_nav.csv"
    if not strat_nav_path.exists():
        print(f"Error: {strat_nav_path} not found. Please run final_champion_run.py first.")
        return

    strat_nav = pd.read_csv(strat_nav_path)
    strat_nav['date'] = pd.to_datetime(strat_nav['date'])
    
    # 2. Load Benchmark (Top 1000)
    # We use DataHandler to ensure consistent loading
    dh = DataHandler(base_path / "database/price_data.parquet")
    # We don't need to load full price data, just benchmarks
    dh.load_benchmarks(base_path / "benchmarks")
    
    if dh.top_1000_bench is None or dh.top_1000_bench.empty:
        print("Error: Benchmark data not found.")
        return
        
    bench_df = dh.top_1000_bench.copy()
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    
    # 3. Align Dates
    start_date = strat_nav['date'].min()
    end_date = strat_nav['date'].max()
    
    # Filter Benchmark to match Strategy range
    bench_df = bench_df[(bench_df['date'] >= start_date) & (bench_df['date'] <= end_date)].copy()
    
    # 4. Normalize Benchmark NAV
    # Start Benchmark NAV at the same initial value as Strategy (10,000,000)
    initial_bench_val = bench_df.iloc[0]['index_value']
    bench_df['nav'] = (bench_df['index_value'] / initial_bench_val) * 10000000
    
    # 5. Calculate Metrics
    strat_metrics = calculate_metrics(strat_nav)
    bench_metrics = calculate_metrics(bench_df[['date', 'nav']])
    
    # 6. Report
    print("\n" + "="*80)
    print("CHAMPION STRATEGY vs. TOP 1000 BENCHMARK (May 2017 - Feb 2026)")
    print("="*80)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    print(f"{'Metric':<20} | {'Strategy (Champ)':<20} | {'Benchmark (Top 1000)':<25}")
    print("-" * 75)
    
    for m in metrics:
        s_val = strat_metrics.get(m, "N/A")
        b_val = bench_metrics.get(m, "N/A")
        print(f"{m:<20} | {s_val:>20} | {b_val:>25}")
        
    print("="*80)
    
    # Alpha Check
    try:
        s_ret = float(strat_metrics['Absolute Return'].strip('%'))
        b_ret = float(bench_metrics['Absolute Return'].strip('%'))
        alpha = s_ret - b_ret
        print(f"\nTotal Alpha Generated: {alpha:.2f}%")
        
        s_cagr = float(strat_metrics['CAGR'].strip('%'))
        b_cagr = float(bench_metrics['CAGR'].strip('%'))
        alpha_cagr = s_cagr - b_cagr
        print(f"Annualized Alpha (CAGR Diff): {alpha_cagr:.2f}%")
    except:
        pass
        
    print("="*80)

if __name__ == "__main__":
    compare_champion_vs_benchmark()
