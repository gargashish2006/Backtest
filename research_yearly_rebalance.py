import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_yearly_backtest():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy
    strategy = ContrarianBreadthStrategy(dh)
    
    # 3. Define Yearly Rebalance Dates (Mid-Feb)
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        d = pd.Timestamp(year=year, month=2, day=15)
        # Find the actual trading day on or before mid-feb
        valid = [dt for dt in all_dates if dt <= d]
        if valid:
            reb_dt = max(valid)
            if reb_dt not in rebalance_dates:
                rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    start_date = "2017-02-15"
    end_date = "2026-02-05"
    
    print(f"Starting Yearly Rebalance Backtest from {start_date}...")
    print(f"Rebalance Dates: {[d.strftime('%Y-%m-%d') for d in rebalance_dates]}")
    
    # 4. Run Backtest
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 5. Report
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*50)
    print("YEARLY REBALANCE STRATEGY PERFORMANCE")
    print("="*50)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    # Simple comparison from memory of recent champion run (Quarterly)
    print("\n" + "="*50)
    print("COMPARISON WITH QUARTERLY CHAMPION")
    print("="*50)
    print(f"{'Metric':<20} | {'Yearly (Feb)':<15} | {'Quarterly (Champ)':<15}")
    print("-" * 55)
    print(f"{'Abs Return (%)':<20} | {stats['Absolute Return']:>15} | {'540.41%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'0.83':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-49.03%':>15}")
    print("="*50)

if __name__ == "__main__":
    run_yearly_backtest()
