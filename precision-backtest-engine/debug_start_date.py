import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def check_start_dates():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")

    # Quarterly Rebalance Dates
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    rebalance_dates.sort()

    dates_to_test = ["2017-02-15", "2017-05-15"]
    
    for start_date in dates_to_test:
        print(f"\nTesting Start Date: {start_date}")
        strategy = ContrarianBreadthStrategy(dh)
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date=start_date,
            end_date="2026-02-05",
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates,
            verbose=False
        )
        
        stats = calculate_metrics(pd.DataFrame(portfolio.nav_history))
        print(f"Start: {start_date} -> Abs Return: {stats['Absolute Return']} | CAGR: {stats['CAGR']}")

if __name__ == "__main__":
    check_start_dates()
