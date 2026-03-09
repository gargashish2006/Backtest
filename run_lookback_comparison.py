import pandas as pd
import numpy as np
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_lookback_comparison():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in quarterly_dates:
                        quarterly_dates.append(reb)
    quarterly_dates.sort()
    
    warnings.filterwarnings('ignore')
    results = []
    
    thresholds = [0.40, 0.50, 0.60]
    lookbacks = [1, 2, 3, 4]
    
    for thresh in thresholds:
        for lookback in lookbacks:
            print(f"\n--- Testing Shield (SH Increase < {thresh:.0%}) with {lookback}Q Lookback ---")
            port = Portfolio(10000000)
            strategy = ContrarianBreadthStrategy(dh, min_history_years=0.0)
            strategy.precompute_rsi(quarterly_dates)
            
            fee_model = FeeModel(0.0015, 0.005)
            tax_man = TaxManager(0.20, 0.125)
            sim = SimEngine(dh, port, fee_model, tax_man)
            
            sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
            
            for today in sim_dates:
                # 1. Technical Exits
                if len(port.holdings) > 0:
                    exits = strategy.check_exits(today, port.holdings)
                    if exits:
                        prices = dh.get_daily_prices(today)
                        for isin in exits:
                            sim._sell_all(isin, today, prices)
                            
                # 2. Rebalance Check + Shield
                if today in quarterly_dates:
                    sh_trend = dh.get_shareholder_trend(today, lookback_quarters=lookback)
                    if not sh_trend.empty:
                        sh_increase_pct = (sh_trend['decreased'] == 0).mean()
                    else:
                        sh_increase_pct = 0.0
                    
                    if sh_increase_pct < thresh:
                        if len(port.holdings) > 0:
                            prices = dh.get_daily_prices(today)
                            for isin in list(port.holdings.keys()):
                                sim._sell_all(isin, today, prices)
                    else:
                        new_target = strategy.calculate_selection(today)
                        prices = dh.get_daily_prices(today)
                        if prices:
                            sim._execute_rebalance(today, new_target, prices)
                            
                # 3. Daily NAV Log
                port.record_nav(today, dh.get_daily_prices(today))
                
            nav_df = pd.DataFrame(port.nav_history)
            stats = calculate_metrics(nav_df)
            results.append({
                'Thresh': f"{thresh:.0%}",
                'Lookback': f"{lookback}Q",
                'CAGR': stats['CAGR'],
                'Sharpe': stats['Sharpe Ratio'],
                'MaxDD': stats['Max Drawdown']
            })

    print("\n" + "="*75)
    print(f"{'Threshold':<10} | {'Lookback':<10} | {'CAGR':<10} | {'Sharpe':<10} | {'Max Drawdown':<15}")
    print("-" * 75)
    for r in results:
        print(f"{r['Thresh']:<10} | {r['Lookback']:<10} | {r['CAGR']:<10} | {r['Sharpe']:<10} | {r['MaxDD']:<15}")
    print("="*75)

    print("\n" + "="*65)
    print(f"{'Lookback':<10} | {'CAGR':<10} | {'Sharpe':<10} | {'Max Drawdown':<15}")
    print("-" * 65)
    for r in results:
        print(f"{r['Lookback']:<10} | {r['CAGR']:<10} | {r['Sharpe']:<10} | {r['MaxDD']:<15}")
    print("="*65)

if __name__ == "__main__":
    run_lookback_comparison()
