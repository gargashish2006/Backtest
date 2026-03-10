import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def compare_champion_vs_sync15():
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
            if valid: rebalance_dates.append(max(valid))
    rebalance_dates.sort()
    
    # Start Date: May 2017 (Standardized)
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date)]

    # 3. Define Strategies
    
    # My "Quarterly Champion" (Current Best)
    my_champion = ContrarianBreadthStrategy(dh,
        max_per_industry=3,
        industry_group_top_pct=0.50,
        industry_decrease_min_pct=0.50,
        rsnp_threshold=0.40
    )
    
    # "Sync15" Replica (External File Logic)
    # Logic: 40% Group, 60% Ind, 0.0 RSNP Filter (Ranking Only), Max 4 Stocks
    sync15_replica = ContrarianBreadthStrategy(dh,
        max_per_industry=4,
        industry_group_top_pct=0.40,
        industry_decrease_min_pct=0.60,
        rsnp_threshold=0.0 # Ranking only, no hard filter
    )
    
    strategies = {
        "My Champion (Top 3, RSNP>0.4)": my_champion,
        "Sync15 (Top 4, No RSNP Filt)": sync15_replica
    }
    
    results = {}

    for name, strategy in strategies.items():
        print(f"\nRunning Backtest: {name}...")
        
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
        results[name] = calculate_metrics(nav_df)

    # 4. Report
    print("\n" + "="*80)
    print("COMPARISON: MY CHAMPION vs. SYNC15 LEGACY")
    print("="*80)
    
    metrics = ["Absolute Return", "CAGR", "Max Drawdown", "Sharpe Ratio"]
    print(f"{'Metric':<20} | {'My Champion':<25} | {'Sync15 Replica':<25}")
    print("-" * 75)
    
    champ = results["My Champion (Top 3, RSNP>0.4)"]
    sync = results["Sync15 (Top 4, No RSNP Filt)"]
    
    for m in metrics:
        print(f"{m:<20} | {champ[m]:>25} | {sync[m]:>25}")
    print("="*80)

if __name__ == "__main__":
    compare_champion_vs_sync15()
