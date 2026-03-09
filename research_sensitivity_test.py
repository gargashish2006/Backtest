import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_sensitivity_test():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date, end_date = "2017-05-15", "2026-02-05"
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date): rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    # Base Parameters (Champion Model)
    base_params = {
        "num_stocks": 15,
        "max_per_industry": 3,
        "rsnp_threshold": 0.40,
        "shareholder_lookback_quarters": 4,
        "rsi_exit_threshold": 39, 
        "industry_decrease_min_pct": 0.50
    }

    results = []

    def run_backtest(name, params):
        strat = ContrarianBreadthStrategy(dh, **params)
        port = Portfolio(10000000)
        eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
        eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
        m = calculate_metrics(pd.DataFrame(port.nav_history))
        return {
            "Test": name,
            "CAGR": m["CAGR"],
            "Sharpe": m["Sharpe Ratio"],
            "MaxDD": m["Max Drawdown"]
        }

    # 1. RSNP Threshold Sensitivity (Base 0.40)
    print("\nTesting RSNP Thresholds...")
    for val in [0.30, 0.35, 0.40, 0.45, 0.50]:
        p = base_params.copy()
        p["rsnp_threshold"] = val
        results.append(run_backtest(f"RSNP > {val:.2f}", p))

    # 2. RSI Exit Level Sensitivity (Base 39)
    print("\nTesting RSI Exit Levels...")
    for val in [30, 35, 39, 45, 50]:
        p = base_params.copy()
        p["rsi_exit_threshold"] = val
        results.append(run_backtest(f"RSI Exit < {val}", p))

    # 3. Shareholder Lookback Sensitivity (Base 4Q)
    print("\nTesting Shareholder Lookback...")
    for val in [3, 4, 5, 6]:
        p = base_params.copy()
        p["shareholder_lookback_quarters"] = val
        results.append(run_backtest(f"Lookback {val}Q", p))
    
    # 4. Industry Decrease Min % (Base 50%)
    print("\nTesting Industry Decrease Threshold...")
    for val in [0.40, 0.50, 0.60]:
        p = base_params.copy()
        p["industry_decrease_min_pct"] = val
        results.append(run_backtest(f"Ind Decr > {val:.0%}", p))

    # 5. Max Per Industry (Base 3)
    print("\nTesting Max Per Industry...")
    for val in [2, 3, 4, 5]:
        p = base_params.copy()
        p["max_per_industry"] = val
        results.append(run_backtest(f"Max {val}/Ind", p))

    print("\n" + "="*80)
    print("SENSITIVITY STRESS TEST RESULTS (Robustness Check)")
    print("="*80)
    print(f"{'Test Parameter':<25} | {'CAGR':>10} | {'Sharpe':>10} | {'MaxDD':>10}")
    print("-" * 80)
    
    # Print grouped by test type
    current_group = ""
    for res in results:
        # Simple grouping check
        test_name = res["Test"]
        group = test_name.split()[0]
        if group != current_group:
            print("-" * 80)
            current_group = group
            
        print(f"{res['Test']:<25} | {res['CAGR']:>10} | {res['Sharpe']:>10} | {res['MaxDD']:>10}")
    print("="*80)

if __name__ == "__main__":
    run_sensitivity_test()
