import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_absolute_both import ContrarianAbsoluteBothStrategy
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def compare_hierarchical_logics():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Strategies
    # Champion: Group=Relative (Top 50%), Industry=Absolute (>=50%)
    strat_champ = ContrarianBreadthStrategy(dh, industry_group_top_pct=0.50, industry_decrease_min_pct=0.50)
    
    # Variant: Group=Absolute (>=50%), Industry=Absolute (>=50%)
    strat_absolute = ContrarianAbsoluteBothStrategy(dh, group_min_pct=0.50, industry_min_pct=0.50)
    
    # 3. Setup Rebalance Dates
    rebalance_dates = []
    all_dates = dh.get_all_dates()
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    # 4. Run Champion
    print("Running Champion (Relative Group / Absolute Industry)...")
    p1 = Portfolio(initial_cash=10000000)
    fee = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    e1 = SimEngine(dh, p1, fee, tax, cash_yield_rate=0.05, cash_tax_rate=0.30)
    e1.run("2017-05-15", "2026-02-05", strat_champ.calculate_selection, rebalance_dates)
    stats_champ = calculate_metrics(pd.DataFrame(p1.nav_history))
    
    # 5. Run Absolute/Absolute
    print("Running Double-Absolute (Absolute Group / Absolute Industry)...")
    p2 = Portfolio(initial_cash=10000000)
    e2 = SimEngine(dh, p2, fee, tax, cash_yield_rate=0.05, cash_tax_rate=0.30)
    e2.run("2017-05-15", "2026-02-05", strat_absolute.calculate_selection, rebalance_dates)
    stats_absolute = calculate_metrics(pd.DataFrame(p2.nav_history))
    
    # 6. Comparison Table
    print("\n" + "="*60)
    print("LOGIC COMPARISON: RELATIVE VS ABSOLUTE GROUP FILTER")
    print("="*60)
    print(f"{'Metric':<20} | {'Champ (Rel Group)':<18} | {'Double Absolute':<18}")
    print("-" * 62)
    print(f"{'Abs Return (%)':<20} | {stats_champ['Absolute Return']:>18} | {stats_absolute['Absolute Return']:>18}")
    print(f"{'CAGR (%)':<20} | {stats_champ['CAGR']:>18} | {stats_absolute['CAGR']:>18}")
    print(f"{'Max Drawdown (%)':<20} | {stats_champ['Max Drawdown']:>18} | {stats_absolute['Max Drawdown']:>18}")
    print(f"{'Sharpe Ratio':<20} | {stats_champ['Sharpe Ratio']:>18} | {stats_absolute['Sharpe Ratio']:>18}")
    print("="*60)

if __name__ == "__main__":
    compare_hierarchical_logics()
