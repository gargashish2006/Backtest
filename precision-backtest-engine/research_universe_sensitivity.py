import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_universe_comparison():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # Setup Rebalance Dates
    rebalance_dates = []
    all_dates = dh.get_all_dates()
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
            
    # Define Tests
    tests = [
        {"name": "Top 1000 (Champion)", "size": 1000},
        {"name": "Top 500 (Large Cap Focus)", "size": 500}
    ]
    
    results = {}

    for test in tests:
        print(f"\nRunning Backtest: {test['name']}...")
        strategy = ContrarianBreadthStrategy(dh, universe_size=test['size'])
        
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date="2017-05-15",
            end_date="2026-02-05",
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        results[test['name']] = calculate_metrics(nav_df)

    # 4. Report
    print("\n" + "="*70)
    print(f"{'Metric':<20} | {'Top 1000 (Champion)':<22} | {'Top 500 (Large Cap)':<22}")
    print("-" * 70)
    
    metrics_to_show = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    for m in metrics_to_show:
        v1 = results["Top 1000 (Champion)"][m]
        v2 = results["Top 500 (Large Cap Focus)"][m]
        print(f"{m:<20} | {v1:>22} | {v2:>22}")
    print("="*70)

if __name__ == "__main__":
    run_universe_comparison()
