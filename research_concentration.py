import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_full_concentration_research():
    # 1. Setup
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Rebalance Dates (Quarterly)
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date):
                    rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    configs = [
        {"name": "15 Stocks", "n": 15},
        {"name": "12 Stocks", "n": 12},
        {"name": "10 Stocks", "n": 10},
        {"name": "7 Stocks", "n": 7}
    ]

    results = {}

    for config in configs:
        print(f"\nRunning Backtest: {config['name']}...")
        strategy = ContrarianBreadthStrategy(
            data_handler=dh,
            num_stocks=config['n'],
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
    print("\n" + "="*120)
    print("PORTFOLIO CONCENTRATION SENSITIVITY ANALYSIS")
    print("="*120)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    headers = [c['name'] for c in configs]
    
    print(f"{'Metric':<20} | {headers[0]:>22} | {headers[1]:>22} | {headers[2]:>22} | {headers[3]:>22}")
    print("-" * 120)
    
    for m in metrics:
        v0 = results[headers[0]][m]
        v1 = results[headers[1]][m]
        v2 = results[headers[2]][m]
        v3 = results[headers[3]][m]
        print(f"{m:<20} | {v0:>22} | {v1:>22} | {v2:>22} | {v3:>22}")
    print("="*120)

if __name__ == "__main__":
    run_full_concentration_research()
