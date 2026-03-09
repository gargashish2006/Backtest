
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from research_1_week_lag import LaggedContrarianStrategy
from utils.analytics import calculate_metrics

def run_strat(dh, strat_class, rdates, start_date, end_date):
    port = Portfolio(10000000)
    fee = FeeModel(0.0015, 0.005)
    tax = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, port, fee, tax, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    strat = strat_class(dh)
    strat.precompute_rsi(rdates)
    
    engine.run(start_date, end_date, strat.calculate_selection, rdates, verbose=False)
    nav_df = pd.DataFrame(port.nav_history)
    metrics = calculate_metrics(nav_df)
    return nav_df, metrics

def plot_comparison():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)])

    print("Running Original Champion...")
    n_orig, m_orig = run_strat(dh, ContrarianBreadthStrategy, rdates, start_date, end_date)
    
    print("Running 1-Week Lagged Champion...")
    n_lag, m_lag = run_strat(dh, LaggedContrarianStrategy, rdates, start_date, end_date)
    
    # 3. Benchmark Logic (Normalised to 10Cr)
    bench = dh.top_1000_bench.copy()
    bench = bench[(bench['date'] >= start_date) & (bench['date'] <= end_date)]
    initial_idx = bench['index_value'].iloc[0]
    bench['nav'] = (bench['index_value'] / initial_idx) * 10000000
    m_bench = calculate_metrics(bench[['date', 'nav']])
    
    # Plotting
    plt.figure(figsize=(12, 7))
    plt.plot(n_orig['date'], n_orig['nav'], label=f"Original Champion (CAGR: {m_orig['CAGR']})", color='#1f77b4', linewidth=1.5)
    plt.plot(n_lag['date'], n_lag['nav'], label=f"Lagged Champion (CAGR: {m_lag['CAGR']})", color='#2ca02c', linewidth=2)
    plt.plot(bench['date'], bench['nav'], label=f"Top 1000 Benchmark (CAGR: {m_bench['CAGR']})", color='#ff7f0e', linestyle='--', alpha=0.7)
    
    plt.title("NAV Comparison: Champion vs Lagged vs Benchmark (2017-2026)", fontsize=14, pad=20)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Portfolio Value (INR)", fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.yscale('log') # Log scale for better compounding visualization
    
    save_path = "/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/nav_comparison.png"
    plt.savefig(save_path)
    print(f"Plot saved to {save_path}")
    
    # Comparison Table
    print("\n" + "="*80)
    print(f"{'Metric':<25} | {'Benchmark (Top 1000)':<20} | {'Original Champion':<20} | {'Lagged Champion':<20}")
    print("-" * 90)
    metrics_to_show = ['Absolute Return', 'CAGR', 'Max Drawdown', 'Sharpe Ratio']
    for m in metrics_to_show:
        print(f"{m:<25} | {m_bench[m]:>20} | {m_orig[m]:>20} | {m_lag[m]:>20}")
    print("="*80)

if __name__ == "__main__":
    plot_comparison()
