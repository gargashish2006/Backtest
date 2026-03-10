import pandas as pd
import numpy as np
from pathlib import Path
import itertools
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_limit_sensitivity():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")

    rsnp_thresholds = [0.40]
    stock_limits = [1, 2, 3]
    results = []

    # Pre-generate rebalance dates
    all_trading_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    print(f"\nEvaluating Final Stock Limit Sensitivity (RSNP:0.40 Champion)...")
    for rsnp, limit in itertools.product(rsnp_thresholds, stock_limits):
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        # Test specific limits
        strategy = ContrarianBreadthStrategy(dh, 
                                            num_stocks=15,
                                            max_per_industry=limit, 
                                            industry_group_top_pct=0.50, 
                                            industry_decrease_min_pct=0.50,
                                            rsnp_threshold=rsnp)

        engine.run(
            start_date="2017-05-15",
            end_date="2026-02-05",
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates,
            verbose=False
        )

        metrics = calculate_metrics(pd.DataFrame(engine.portfolio.nav_history))
        results.append({
            'RSNP_Threshold': rsnp,
            'Stock_Limit': limit,
            'Abs_Return': metrics['Absolute Return'],
            'CAGR': metrics['CAGR'],
            'Max_DD': metrics['Max Drawdown'],
            'Sharpe': metrics['Sharpe Ratio']
        })
        print(f"Limit:{limit} -> Return: {metrics['Absolute Return']} | DD: {metrics['Max Drawdown']}")

    df = pd.DataFrame(results)
    output_file = "/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/outputs/sensitivity_analysis_limits.csv"
    df.to_csv(output_file, index=False)
    print(f"\nAnalysis Complete. Saved to {output_file}")

if __name__ == "__main__":
    run_limit_sensitivity()
