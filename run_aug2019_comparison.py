import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_comparison():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # NEW PERIOD: Feb 2022 onwards
    start_date = "2022-02-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    # Rebalance dates from Aug 2019 onwards
    for year in range(2019, 2027):
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
    
    variations = [
        ("No Filter", 0.0), 
        ("1.5Yr Filter", 1.5), 
        ("2Yr Filter", 2.0),
        ("5Yr Filter", 5.0)
    ]
    
    for label, min_hist in variations:
        print(f"\n--- Running: {label} ({start_date} -> {end_date}) ---")
        port = Portfolio(10000000)
        strategy = ContrarianBreadthStrategy(dh, min_history_years=min_hist)
        eng = SimEngine(dh, port, fee_model, tax_man)
        eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=False)
        
        nav_df = pd.DataFrame(port.nav_history)
        stats = calculate_metrics(nav_df)
        results[label] = stats
        
        # Save NAVs
        nav_df.to_csv(repo_root / f"outputs/aug19_{label.replace(' ', '_').lower()}.csv", index=False)

    print("\n" + "="*50)
    print(f"RESULTS FOR PERIOD: {start_date} to {end_date}")
    print("="*50)
    print(f"{'Variation':<15} | {'CAGR':<10} | {'Sharpe':<10} | {'Max DD':<10}")
    print("-" * 50)
    for label, stats in results.items():
        print(f"{label:<15} | {stats['CAGR']:<10} | {stats['Sharpe Ratio']:<10} | {stats['Max Drawdown']:<10}")

if __name__ == "__main__":
    run_comparison()
