
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.ml_strategy_v2 import MLStrategyV2
from utils.analytics import calculate_metrics

def run_ml_backtest_training_v2():
    repo_root = Path(__file__).parent
    
    # 1. Setup
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 2. Strategy
    model_path = repo_root / "models/ml_model_rf_v2.pkl"
    if not model_path.exists():
        print("ML Model V2 not found!")
        return
        
    print(f"Initializing ML Strategy V2 with model: {model_path.name}")
    strategy = MLStrategyV2(dh, model_path)
    
    # 3. Backtest Period (In-Sample / Training Period)
    # May 2017 - Feb 2023 
    # (Matches the training data range roughly, dataset gen started 2017-05-15)
    start_date = "2017-05-15"
    end_date = "2023-02-14"
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    
    for year in range(2017, 2024):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))
    
    print(f"Backtesting V2 (Training Period) from {start_date} to {end_date}...")
    print(f"Rebalance Dates: {len(rebalance_dates)} periods")
    
    warnings.filterwarnings('ignore')
    
    # 4. Run Simulation
    port = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125) # Standard Tax
    eng = SimEngine(dh, port, fee_model, tax_man)
    
    eng.run(start_date, end_date, strategy.calculate_selection, rebalance_dates, verbose=False) # Verbose false to reduce noise
    
    # 5. Results
    nav_df = pd.DataFrame(port.nav_history)
    output_path = repo_root / "outputs/ml_strategy_v2_training_nav.csv"
    nav_df.to_csv(output_path, index=False)
    
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("ML STRATEGY V2 PERFORMANCE (TRAINING PERIOD: 2017-2023)")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<20} : {v}")
    print("="*60)
    print(f"Final NAV: {port.nav_history[-1]['nav']:,.2f}")
    print(f"Total Costs: {eng.fee_model.total_fees:,.2f}")
    print(f"Total Taxes: {sum(t['total_tax'] for t in eng.tax_man.tax_paid_history):,.2f}")
    print("="*60)

if __name__ == "__main__":
    run_ml_backtest_training_v2()
