
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_champion_full_period():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # FULL PERIOD (2017-2026)
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
    
    print(f"\nRunning Champion Strategy (Post-Tax/Fees) - Full Period {start_date} to {end_date}...")
    
    # Initialize Portfolio
    port = Portfolio(10000000)
    
    # Initialize Core Champion Strategy (ContrarianBreadthStrategy)
    # Using default parameters as per user preference (Top 1000, Liq Filter, etc.)
    strategy = ContrarianBreadthStrategy(dh)
    
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    eng = SimEngine(dh, port, fee_model, tax_man)
    
    eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=True)
    
    nav_df = pd.DataFrame(port.nav_history)
    stats = calculate_metrics(nav_df)
    
    print(f"\n  >>> Champion Result: CAGR {stats['CAGR']}, Sharpe {stats['Sharpe Ratio']}, DD {stats['Max Drawdown']}")
    
    # Save NAV
    output_path = repo_root / "outputs/champion_full_nav.csv"
    nav_df.to_csv(output_path, index=False)
    print(f"NAV saved to {output_path}")

if __name__ == "__main__":
    run_champion_full_period()
