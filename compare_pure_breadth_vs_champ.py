import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.industry_momentum_rsnp import IndustryMomentumRSNPStrategy
from utils.analytics import calculate_metrics

def compare_momentum_rsnp():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_handler = DataHandler(base_path / "database/price_data.parquet")
    data_handler.load_data()
    data_handler.load_benchmarks(base_path / "benchmarks")

    # 2. Setup Industry Momentum RSNP (Pure Breadth Momentum)
    # Using rsnp_threshold=0.33 as per its file defaults
    strategy = IndustryMomentumRSNPStrategy(data_handler, rsnp_threshold=0.33)

    # 3. Setup Engine
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(data_handler, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)

    # 4. Generate Rebalance Dates
    all_dates = data_handler.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    # 5. Run Strategy
    print("Running Pure Breadth Momentum (IndustryMomentumRSNP)...")
    engine.run(
        start_date="2017-05-15",
        end_date="2026-02-05",
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )

    # 6. Report
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*50)
    print("PURE BREADTH MOMENTUM (NO SHAREHOLDER FILTER)")
    print("="*50)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    # Compare with our Champion (Retrieved from Logs)
    print("\n" + "="*50)
    print("COMPARISON WITH CHAMPION (CONTRARIAN BREADTH 0.40)")
    print("="*50)
    print(f"{'Metric':<20} | {'Pure Breadth':<15} | {'Champ (Contrarian)':<15}")
    print("-" * 55)
    print(f"{'Abs Return (%)':<20} | {stats['Absolute Return']:>15} | {'540.41%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-49.03%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'0.83':>15}")
    print("="*50)

if __name__ == "__main__":
    compare_momentum_rsnp()
