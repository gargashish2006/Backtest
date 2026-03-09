import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_sticky import ContrarianStickyStrategy
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_sticky_champion_comparison():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Define Rebalance Dates (Quarterly)
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    start_date = "2017-05-15" # Original champion start
    end_date = "2026-02-05"
    
    # Run Both Strategies
    strats = {
        "Original Champion (Turnover)": ContrarianBreadthStrategy(dh),
        "Sticky Champion (Retention)": ContrarianStickyStrategy(dh)
    }
    
    results = {}
    
    for name, strategy_obj in strats.items():
        print(f"\nRunning {name}...")
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date=start_date,
            end_date=end_date,
            strategy_func=strategy_obj.calculate_selection,
            rebalance_dates=rebalance_dates
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        results[name] = calculate_metrics(nav_df)
        
    # Report
    print("\n" + "="*80)
    print("STICKY VS ORIGINAL CHAMPION COMPARISON")
    print("="*80)
    
    metrics = ['Absolute Return', 'CAGR', 'Max Drawdown', 'Sharpe Ratio']
    print(f"{'Metric':<20} | {'Original':<15} | {'Sticky':<15}")
    print("-" * 60)
    
    orig = results["Original Champion (Turnover)"]
    sticky = results["Sticky Champion (Retention)"]
    
    for m in metrics:
        print(f"{m:<20} | {orig[m]:>15} | {sticky[m]:>15}")
    print("="*80)

if __name__ == "__main__":
    run_sticky_champion_comparison()
