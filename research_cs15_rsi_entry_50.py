
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

def run_research():
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

    # 1. Setup Strategy (RSI entry threshold = 50)
    strategy = CS15Strategy(dh, rsi_threshold=50)
    strategy.precompute_rsi(rdates)
    
    # 2. Setup Simulation
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005) 
    tax_manager = TaxManager(0.20, 0.125) 
    
    engine = SimEngine(dh, portfolio, fee_model, tax_manager, 
                        cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 3. Run
    print("Running CS15 (RSI Entry > 50) Backtest...")
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
    
    # 4. Results
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*40)
    print("CS15 (RSI ENTRY > 50) PERFORMANCE")
    print("="*40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*40)

if __name__ == "__main__":
    run_research()
