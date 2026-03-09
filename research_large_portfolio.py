import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_large_portfolio_backtest():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Strategies
    # Variation: 20 Stocks, Max 3 per industry
    strategy_20_3 = ContrarianBreadthStrategy(dh, num_stocks=20, max_per_industry=3)
    
    # 3. Setup Rebalance Dates
    rebalance_dates = []
    all_dates = dh.get_all_dates()
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    # 4. Run Backtest
    print("Starting Large Portfolio Backtest (20 Stocks, Max 3/Ind)...")
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date="2017-05-15",
        end_date="2026-02-05",
        strategy_func=strategy_20_3.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 5. Report
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*50)
    print("LARGE PORTFOLIO PERFORMANCE (20 Stocks, Max 3/Ind)")
    print("="*50)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    # Compare with Champion
    print("\n" + "="*50)
    print("COMPARISON WITH CHAMPION (15 Stocks, Max 3/Ind)")
    print("="*50)
    print(f"{'Metric':<20} | {'Large (20/4)':<15} | {'Champ (15/3)':<15}")
    print("-" * 55)
    print(f"{'Abs Return (%)':<20} | {stats['Absolute Return']:>15} | {'540.41%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-49.03%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'0.83':>15}")
    print("="*50)

if __name__ == "__main__":
    run_large_portfolio_backtest()
