import pandas as pd
from pathlib import Path
import sys

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.append(str(repo_root))

from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics
import matplotlib.pyplot as plt

def run_variant(dh, variant_name, benchmark_type, start_date, end_date, rdates):
    print(f"\n--- Running CS15 Variant: {variant_name} ({benchmark_type} RSNP) ---")
    strategy = CS15Strategy(dh, rsnp_benchmark=benchmark_type)
    strategy.precompute_rsi(rdates)
    
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005) # 0.15% fee, 0.5% impact
    tax_manager = TaxManager(0.20, 0.125) # 20% STCG, 12.5% LTCG
    
    engine = SimEngine(dh, portfolio, fee_model, tax_manager, cash_yield_rate=0.05, cash_tax_rate=0.30)
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
    
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    return nav_df, stats

def run_comparison():
    repo_root = Path(__file__).parent.parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-03-06"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            if d > pd.Timestamp(end_date):
                continue
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted(list(set([d for d in rdates if d >= pd.Timestamp(start_date)])))

    variants = {
        'CS15 Standard': 'top_1000',
        'CS15 Nifty 500': 'nifty_500'
    }
    
    results = {}
    for name, bench in variants.items():
        nav_df, stats = run_variant(dh, name, bench, start_date, end_date, rdates)
        results[name] = {'nav': nav_df, 'stats': stats}
        
    print("\n" + "="*60)
    print("CS15 BENCHMARK COMPARISON RESULTS")
    print("="*60)
    
    metrics_to_print = ['Absolute Return', 'CAGR', 'Max Drawdown', 'Sharpe Ratio']
    
    # Print Header
    header = f"{'Metric':<20} | " + " | ".join([f"{name:<20}" for name in variants.keys()])
    print(header)
    print("-" * len(header))
    
    for metric in metrics_to_print:
        row = f"{metric:<20} | "
        for name in variants.keys():
            val = results[name]['stats'].get(metric, 'N/A')
            row += f"{str(val):<20} | "
        print(row)
    print("="*60)

    # Plot Comparison
    plt.figure(figsize=(12, 6))
    for name in variants.keys():
        nav = results[name]['nav']
        nav['date'] = pd.to_datetime(nav['date'])
        nav = nav.sort_values('date')
        nav['nav_scaled'] = (nav['nav'] / nav['nav'].iloc[0]) * 100
        
        cagr = results[name]['stats'].get('CAGR', 'N/A')
        plt.plot(nav['date'], nav['nav_scaled'], label=f"{name} (CAGR: {cagr})", linewidth=2)
        
    plt.title('CS15 Strategy Benchmark Comparison', fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Normalized Value (Base 100)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left', fontsize=12)
    plt.tight_layout()
    
    plot_path = repo_root / "cs15_benchmark_comparison.png"
    plt.savefig(plot_path, dpi=300)
    print(f"\nPlot saved to {plot_path}")

if __name__ == "__main__":
    run_comparison()
