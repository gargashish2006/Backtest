
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.rsi_exit_strategy import RSIExitStrategy
from utils.analytics import calculate_metrics

def run_rsi_exit_research():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2023-02-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    for year in range(2023, 2027):
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
    
    print(f"\nRunning RSI Exit Research ({start_date} to {end_date})...")
    
    # 3. Strategy
    strategy = RSIExitStrategy(dh)
    
    port = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    eng = SimEngine(dh, port, fee_model, tax_man)
    
    eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=True)
    
    nav_df = pd.DataFrame(port.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print(f"RSI EXIT STRATEGY RESULTS ({start_date} - {end_date})")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<20} : {v}")
    print("="*60)
    
    # Save Results
    nav_df.to_csv(repo_root / "outputs/rsi_exit_nav.csv", index=False)
    
    # Compare with Thesis Breach (Best so far)
    try:
        thesis_nav = pd.read_csv(repo_root / "outputs/dynamic_Thesis_Breach_nav.csv")
        # Ensure date format
        thesis_nav['date'] = pd.to_datetime(thesis_nav['date'])
        # Filter dates
        thesis_nav = thesis_nav[(thesis_nav['date'] >= pd.Timestamp(start_date)) & (thesis_nav['date'] <= pd.Timestamp(end_date))]
        if not thesis_nav.empty:
            t_stats = calculate_metrics(thesis_nav)
            print(f"\nVS THESIS BREACH (Ref):")
            print(f"CAGR: {t_stats['CAGR']} (Diff: {float(stats['CAGR'].strip('%')) - float(t_stats['CAGR'].strip('%')):.2f}%)")
    except Exception as e:
        print(f"Comparison skipped: {e}")

if __name__ == "__main__":
    run_rsi_exit_research()
