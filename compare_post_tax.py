
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

def compare():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)])

    # Setup Common Components
    fee_model = FeeModel(0.0015, 0.005) 
    tax_manager_champ = TaxManager(0.20, 0.125)
    tax_manager_cs15 = TaxManager(0.20, 0.125)
    
    # 1. Run Original Champion (No Lag)
    print("\nRunning Original Champion (Post-Tax, No Lag)...")
    p_champ = Portfolio(10000000)
    strat_champ = ContrarianBreadthStrategy(dh)
    strat_champ.precompute_rsi(rdates)
    engine_champ = SimEngine(dh, p_champ, fee_model, tax_manager_champ, cash_yield_rate=0.05, cash_tax_rate=0.30)
    engine_champ.run(start_date, end_date, strat_champ.calculate_selection, rdates, verbose=False)
    stats_champ = calculate_metrics(pd.DataFrame(p_champ.nav_history))

    # 2. Run CS15 Dynamic
    print("\nRunning CS15 Dynamic (Post-Tax, 7-Day Lag)...")
    p_cs15 = Portfolio(10000000)
    strat_cs15 = CS15Strategy(dh)
    strat_cs15.precompute_rsi(rdates)
    engine_cs15 = SimEngine(dh, p_cs15, fee_model, tax_manager_cs15, cash_yield_rate=0.05, cash_tax_rate=0.30)
    engine_cs15.run(start_date, end_date, strat_cs15.calculate_selection, rdates, verbose=False)
    stats_cs15 = calculate_metrics(pd.DataFrame(p_cs15.nav_history))

    print("\n" + "="*60)
    print(f"{'Metric':<25} | {'Champion (No Lag)':<20} | {'CS15 (Lagged)':<20}")
    print("-"*60)
    for k in stats_champ.keys():
        print(f"{k:<25} | {stats_champ[k]:<20} | {stats_cs15.get(k, 'N/A'):<20}")
    print("="*60)

if __name__ == "__main__":
    compare()
