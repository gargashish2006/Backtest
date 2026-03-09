import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def get_rebalance_dates(all_dates, months, start_date):
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in months:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date):
                    rebalance_dates.append(reb)
    return sorted(list(set(rebalance_dates)))

def run_rebalance_frequency_research():
    # 1. Setup
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-02-05"
    all_dates = dh.get_all_dates()

    configs = [
        {"name": "Quarterly (Standard)", "months": [2, 5, 8, 11]},
        {"name": "6-Monthly (May/Nov)", "months": [5, 11]},
        {"name": "6-Monthly (Feb/Aug)", "months": [2, 8]}
    ]

    results = {}

    for config in configs:
        print(f"\nRunning Backtest: {config['name']}...")
        rebalance_dates = get_rebalance_dates(all_dates, config['months'], start_date)
        
        strategy = ContrarianBreadthStrategy(
            data_handler=dh,
            num_stocks=10, # Using the Elite 10-stock base
            rsnp_threshold=0.4,
            rsi_threshold=40,
            rsi_exit_threshold=39
        )
        
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
        results[config['name']] = calculate_metrics(nav_df)

    # 4. Report
    print("\n" + "="*110)
    print("REBALANCE FREQUENCY ANALYSIS (QUARTERLY VS 6-MONTHLY)")
    print("="*110)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = [c['name'] for c in configs]
    
    print(f"{'Metric':<20} | {headers[0]:>22} | {headers[1]:>28} | {headers[2]:>28}")
    print("-" * 110)
    
    for m in metrics:
        vals = [results[h][m] for h in headers]
        print(f"{m:<20} | {vals[0]:>22} | {vals[1]:>28} | {vals[2]:>28}")
    print("="*110)

if __name__ == "__main__":
    run_rebalance_frequency_research()
