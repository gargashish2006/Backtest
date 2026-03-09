import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_rsi_filter_test():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Define Rebalance Dates (Quarterly) - Consistent with Champion
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
        {"name": "Champion (No RSI)", "rsi_val": 0},
        {"name": "Champion (RSI > 40)", "rsi_val": 40},
        {"name": "Champion (RSI > 50)", "rsi_val": 50}
    ]
    
    results = {}

    for test in tests:
        print(f"\nRunning Backtest: {test['name']}...")
        strategy = ContrarianBreadthStrategy(dh, rsi_threshold=test['rsi_val'])
        
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
    print("WEEKLY RSI FILTER SENSITIVITY (Quarterly Champion)")
    print("="*80)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = [t['name'] for t in tests]
    print(f"{'Metric':<20} | {headers[0]:<20} | {headers[1]:<20} | {headers[2]:<20}")
    print("-" * 90)
    
    for m in metrics:
        v0 = results[headers[0]][m]
        v1 = results[headers[1]][m]
        v2 = results[headers[2]][m]
        print(f"{m:<20} | {v0:>20} | {v1:>20} | {v2:>20}")
    print("="*80)

if __name__ == "__main__":
    run_rsi_filter_test()
