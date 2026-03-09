import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_rsi_exit_test():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Rebalance Dates (Quarterly)
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find closest valid date
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date):
                    rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))
    
    # 3. Define Strategies
    tests = [
        {"name": "Champion (RSI > 40)", "rsi_val": 40, "exit_rsi": 0}, # Baseline (No Exit)
        {"name": "Champion (Exit < 39)", "rsi_val": 40, "exit_rsi": 39} # New Exit Rule
    ]
    
    results = {}

    for test in tests:
        print(f"\nRunning Backtest: {test['name']}...")
        strategy = ContrarianBreadthStrategy(dh, rsi_threshold=test['rsi_val'], rsi_exit_threshold=test['exit_rsi'])
        
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date=start_date,
            end_date=end_date,
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates,
            verbose=False
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        results[test['name']] = calculate_metrics(nav_df)

    # 4. Report
    print("\n" + "="*80)
    print("RSI EXIT RULE SENSITIVITY")
    print("="*80)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = [t['name'] for t in tests]
    print(f"{'Metric':<20} | {headers[0]:<25} | {headers[1]:<25}")
    print("-" * 75)
    
    for m in metrics:
        v0 = results[headers[0]][m]
        v1 = results[headers[1]][m]
        print(f"{m:<20} | {v0:>25} | {v1:>25}")
    print("="*80)

if __name__ == "__main__":
    run_rsi_exit_test()
