"""
Compare CS15 (original) vs CS15-BPF (with 12Q Breadth Pre-Filter) from May 2019.
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from strategies.cs15_breadth_prefilter_strategy import CS15BreadthPreFilterStrategy
from utils.analytics import calculate_metrics

def run_comparison():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2019-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2019, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)])

    fee_model = FeeModel(0.0015, 0.005)
    tax_manager = TaxManager(0.20, 0.125)
    
    results = {}
    
    for name, StratClass in [("CS15 (Original)", CS15Strategy), ("CS15-BPF (+ 12Q Breadth)", CS15BreadthPreFilterStrategy)]:
        print(f"\n{'='*50}")
        print(f"Running: {name}")
        print(f"{'='*50}")
        
        strategy = StratClass(dh)
        strategy.precompute_rsi(rdates)
        
        portfolio = Portfolio(10000000)
        engine = SimEngine(dh, portfolio, fee_model, tax_manager,
                          cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        stats = calculate_metrics(nav_df)
        
        results[name] = {'nav': nav_df, 'stats': stats}
        
        print(f"\n{name} Performance:")
        for k, v in stats.items():
            print(f"  {k:<25}: {v}")
    
    # Load benchmark
    bench = pd.read_parquet(repo_root / "benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.parquet")
    bench['date'] = pd.to_datetime(bench['date'])
    bench = bench[bench['date'] >= pd.Timestamp(start_date)]
    bench['nav_norm'] = bench['index_value'] / bench.iloc[0]['index_value'] * 100
    
    # Plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = {'CS15 (Original)': '#2563eb', 'CS15-BPF (+ 12Q Breadth)': '#dc2626'}
    for name, data in results.items():
        nav = data['nav']
        nav['date'] = pd.to_datetime(nav['date'])
        nav['nav_norm'] = nav['nav'] / nav.iloc[0]['nav'] * 100
        ax.plot(nav['date'], nav['nav_norm'], label=name, linewidth=2, color=colors[name])
    
    ax.plot(bench['date'], bench['nav_norm'], label='Top 1000 EW Benchmark', 
            linewidth=1.5, color='grey', linestyle='--', alpha=0.7)
    
    ax.set_title('CS15 (Original) vs CS15-BPF (+ 12Q Shareholder Breadth Pre-Filter)\nMay 2019 - Feb 2026', 
                fontsize=14, fontweight='bold')
    ax.set_ylabel('NAV (normalized to 100)')
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    
    plt.tight_layout()
    out_path = repo_root / "cs15_vs_bpf_comparison.png"
    plt.savefig(out_path, dpi=150)
    print(f"\nPlot saved to: {out_path}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"{'Metric':<25} {'CS15 (Original)':>17} {'CS15-BPF (+12Q)':>17}")
    print(f"{'='*60}")
    for metric in results['CS15 (Original)']['stats']:
        v1 = results['CS15 (Original)']['stats'][metric]
        v2 = results['CS15-BPF (+ 12Q Breadth)']['stats'][metric]
        print(f"{metric:<25} {str(v1):>17} {str(v2):>17}")
    print(f"{'='*60}")

if __name__ == "__main__":
    run_comparison()
