
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_dampening_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()
    
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    # Test distinct levels of Lookback (Signal Dampening)
    # 4Q = Standard
    # 6Q = 1.5 Years
    # 8Q = 2 Years
    # 12Q = 3 Years
    lookbacks = [4, 6, 8, 12]
    results = []

    print(f"{'Lookback (Q)':<12} | {'CAGR':<8} | {'Max DD':<8} | {'Sharpe':<8}")
    print("-" * 45)

    for q in lookbacks:
        strategy = ContrarianBreadthStrategy(dh, shareholder_lookback_quarters=q, num_stocks=15, max_per_industry=3)
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(start_date="2017-05-15", end_date="2026-02-05", 
                  strategy_func=strategy.calculate_selection, rebalance_dates=rebalance_dates, verbose=False)
        
        metrics = calculate_metrics(pd.DataFrame(portfolio.nav_history))
        results.append({'lookback': q, 'metrics': metrics})
        print(f"{q:<12} | {metrics['CAGR']:<8} | {metrics['Max Drawdown']:<8} | {metrics['Sharpe Ratio']:<8}")

if __name__ == "__main__":
    run_dampening_analysis()
