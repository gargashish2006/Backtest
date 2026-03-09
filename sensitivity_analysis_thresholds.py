import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from strategies.contrarian_benchmark import ContrarianBenchmarkStrategy
from utils.analytics import calculate_metrics
import itertools

def run_sensitivity():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")

    group_thresholds = [0.40, 0.45, 0.50, 0.55, 0.60]
    industry_thresholds = [0.40, 0.45, 0.50, 0.55, 0.60]
    strategies = ["Breadth"] # Only Breadth variant for this run
    
    results = []

    # Pre-generate rebalance dates to save time
    all_trading_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    for strat_type in strategies:
        print(f"\nEvaluating {strat_type} Strategy Sensitivity (RSNP Threshold: 0.34)...")
        for g_pct, i_pct in itertools.product(group_thresholds, industry_thresholds):
            # Setup fresh environment
            portfolio = Portfolio(initial_cash=10000000)
            fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
            tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
            engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
            
            # Using RSNP Threshold 0.34
            strategy = ContrarianBreadthStrategy(dh, max_per_industry=3, 
                                                industry_group_top_pct=g_pct, 
                                                industry_decrease_min_pct=i_pct,
                                                rsnp_threshold=0.34)

            # Run Backtest
            engine.run(
                start_date="2017-05-15",
                end_date="2026-02-05",
                strategy_func=strategy.calculate_selection,
                rebalance_dates=rebalance_dates,
                verbose=False
            )
            
            # Analyze
            nav_df = pd.DataFrame(portfolio.nav_history)
            if not nav_df.empty:
                stats = calculate_metrics(nav_df)
                res = {
                    'Strategy': strat_type,
                    'Group_Top_%': int(g_pct * 100),
                    'Industry_Min_%': int(i_pct * 100),
                    'Abs_Return': stats.get('Absolute Return', '0%'),
                    'CAGR': stats.get('CAGR', '0%'),
                    'Max_DD': stats.get('Max Drawdown', '0%'),
                    'Sharpe': stats.get('Sharpe Ratio', 0)
                }
                results.append(res)
                print(f"G:{int(g_pct*100)}% I:{int(i_pct*100)}% -> Return: {res['Abs_Return']} | DD: {res['Max_DD']}")
            else:
                print(f"G:{int(g_pct*100)}% I:{int(i_pct*100)}% -> NO DATA")

    # Save results
    final_df = pd.DataFrame(results)
    final_df.to_csv(base_path / "outputs/sensitivity_analysis_thresholds.csv", index=False)
    print("\nSensitivity Analysis Complete. Saved to outputs.")

if __name__ == "__main__":
    run_sensitivity()
