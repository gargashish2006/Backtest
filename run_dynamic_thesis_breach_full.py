
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.dynamic_holding_strategy import DynamicHoldingStrategy
from utils.analytics import calculate_metrics

def run_thesis_breach_full():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 2. Strategy: Thesis Breach (Shareholder Increase Exit)
    print("Initializing Dynamic Holding Strategy (Exit: Thesis Breach)...")
    strategy = DynamicHoldingStrategy(dh, exit_mode='thesis_breach')
    
    # 3. Backtest Period (Full History)
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
    
    print(f"Running Full Backtest ({start_date} to {end_date})...")
    warnings.filterwarnings('ignore')
    
    # 4. Run Simulation
    port = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    eng = SimEngine(dh, port, fee_model, tax_man)
    
    eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=True)
    
    # 5. Results
    nav_df = pd.DataFrame(port.nav_history)
    output_path = repo_root / "outputs/dynamic_thesis_breach_full_nav.csv"
    nav_df.to_csv(output_path, index=False)
    
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("THESIS BREACH STRATEGY (FULL PERIOD 2017-2026)")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<20} : {v}")
    print("="*60)
    print(f"Final NAV: {port.nav_history[-1]['nav']:,.2f}")

if __name__ == "__main__":
    run_thesis_breach_full()
