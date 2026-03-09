import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_semiannual_backtest():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy
    strategy = ContrarianBreadthStrategy(dh)
    
    # 3. Define Semi-Annual Rebalance Dates (Feb 15 and Aug 15)
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 8]: # Feb and Aug
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find the actual trading day on or before mid-month
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    start_date = "2017-02-15"
    end_date = "2026-02-05"
    
    print(f"Starting Semi-Annual (Feb/Aug) Backtest...")
    print(f"First Rebalance: {rebalance_dates[0]}")
    
    # 4. Run Backtest
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
    
    # 5. Report
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("SEMI-ANNUAL REBALANCE (FEB/AUG) PERFORMANCE")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    print("\n" + "="*60)
    print("COMPARISON WITH OTHER FREQUENCIES")
    print("="*60)
    print(f"{'Metric':<20} | {'Semi-Annual':<15} | {'Yearly (May)':<15} | {'Quarterly':<15}")
    print("-" * 65)
    print(f"{'Abs Return (%)':<20} | {stats['Absolute Return']:>15} | {'1196.17%':>15} | {'524.24%':>15}")
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'34.12%':>15} | {'23.35%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-54.50%':>15} | {'-49.03%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'1.11':>15} | {'0.82':>15}")
    print("="*60)

if __name__ == "__main__":
    run_semiannual_backtest()
