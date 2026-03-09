
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth_top1000 import ContrarianBreadthTop1000Strategy
from utils.analytics import calculate_metrics

def run_restoration():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup Strategy (RESTORED logic)
    strategy = ContrarianBreadthTop1000Strategy(dh)
    
    # 2. Setup Portfolio & Engine (Current baseline config: 0.98/0.05)
    port = Portfolio(initial_cash=10000000)
    fee = FeeModel(0.0015, 0.005)
    tax = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, port, fee, tax, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 3. Define Rebalance Dates
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v:
                rdates.append(max(v))
    rdates.sort()
    rdates = [r for r in rdates if r >= pd.Timestamp('2017-05-15') and r <= pd.Timestamp('2026-02-05')]
    
    # Calculate RSI
    strategy.precompute_rsi(rdates)
    
    # 4. Run Simulation
    print("Running Restoration Simulation (Top 1000 Breadth Filter)...")
    engine.run('2017-05-15', '2026-02-05', strategy.calculate_selection, rdates, verbose=False)
    
    # 5. Report Metrics
    nav_df = pd.DataFrame(port.nav_history)
    metrics = calculate_metrics(nav_df)
    
    print("\n" + "="*50)
    print("RESTORATION RESULTS")
    print("="*50)
    for k, v in metrics.items():
        print(f"{k:<20}: {v}")
    print("="*50)

if __name__ == "__main__":
    run_restoration()
