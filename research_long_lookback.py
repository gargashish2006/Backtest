import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_long_lookback_comparison():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Define Rebalance Dates (Quarterly)
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2018, 2027): # Start generating from 2018
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    
    # Filter for the specific start date requested
    start_date = "2018-05-15"
    end_date = "2026-02-05"
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)]
    
    # 3. Define Strategies
    tests = [
        {"name": "Champion (4 Qtrs / 1 Yr)", "lookback": 4},
        {"name": "6 Qtrs / 1.5 Yrs", "lookback": 6},
        {"name": "8 Qtrs / 2 Yrs", "lookback": 8}
    ]
    
    results = {}

    for test in tests:
        print(f"\nRunning Backtest: {test['name']} (Start: {start_date})...")
        strategy = ContrarianBreadthStrategy(dh, shareholder_lookback_quarters=test['lookback'])
        
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date=start_date, # Explicit start date
            end_date=end_date,
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        results[test['name']] = calculate_metrics(nav_df)

    # 4. Report
    print("\n" + "="*90)
    print(f"SHAREHOLDER LOOKBACK COMPARISON (MAY 2018 - FEB 2026)")
    print("="*90)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = [t['name'] for t in tests]
    
    # Dynamic formatting based on number of columns
    header_str = f"{'Metric':<20} | " + " | ".join([f"{h:<20}" for h in headers])
    print(header_str)
    print("-" * len(header_str))
    
    for m in metrics:
        row_str = f"{m:<20} | "
        for h in headers:
            val = results[h][m]
            row_str += f"{val:>20} | "
        print(row_str[:-2]) # Trim last separator
    print("="*90)

if __name__ == "__main__":
    run_long_lookback_comparison()
