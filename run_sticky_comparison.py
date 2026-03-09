import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_sticky_comparison():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # Starting from May 2017 onwards
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in quarterly_dates:
                        quarterly_dates.append(reb)
    quarterly_dates.sort()
    
    warnings.filterwarnings('ignore')
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    
    results = {}
    
    # Variations to compare
    variations = [
        ("Baseline (Fresh Selection)", 0.0),
        ("Sticky Industry (RSNP > 0.5)", 0.5)
    ]
    
    for label, sticky_thresh in variations:
        print(f"\n--- Running Variation: {label} ---")
        port = Portfolio(10000000)
        # Using 0-year history filter (Original Champion)
        strategy = ContrarianBreadthStrategy(dh, min_history_years=0.0, sticky_rsnp_threshold=sticky_thresh)
        eng = SimEngine(dh, port, fee_model, tax_man)
        eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=False)
        
        nav_df = pd.DataFrame(port.nav_history)
        stats = calculate_metrics(nav_df)
        results[label] = stats
        
    print("\n" + "="*60)
    print(f"STICKY INDUSTRY VARIATION RESULTS (Feb 2022 - Feb 2026)")
    print("="*60)
    print(f"{'Variation':<25} | {'CAGR':<10} | {'Sharpe':<10} | {'Max DD':<10}")
    print("-" * 60)
    for label, stats in results.items():
        print(f"{label:<25} | {stats['CAGR']:<10} | {stats['Sharpe Ratio']:<10} | {stats['Max Drawdown']:<10}")

if __name__ == "__main__":
    run_sticky_comparison()
