import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from utils.analytics import calculate_metrics
from strategies.industry_shareholding import IndustryShareholdingStrategy as RSNPStrategy
from strategies.industry_shareholding_momentum import IndustryShareholdingMomentumStrategy as MomentumStrategy

def run_variation(dh, name, strategy_class):
    print(f"\nRUNNING: {name} (Max 3 per industry)")
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0007, impact_cost_rate=0.001)
    tax_man = TaxManager()
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    strategy = strategy_class(dh, max_per_industry=3)
    
    rebalance_dates = []
    all_dates = dh.get_all_dates()
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                rebalance_dates.append(max(valid))
    
    engine.run(start_date="2017-05-15", end_date="2026-02-05", strategy_func=strategy.calculate_selection, rebalance_dates=rebalance_dates)
    
    # Calculate stats
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    print(f"RESULTS FOR {name}:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return stats

def compare_variations():
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    run_variation(dh, "Shareholding + RSNP", RSNPStrategy)
    run_variation(dh, "Shareholding + Momentum", MomentumStrategy)

if __name__ == "__main__":
    compare_variations()
