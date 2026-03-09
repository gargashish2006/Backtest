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

def run_sh_increase_risk_research():
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
    
    # 2. Setup Components
    warnings.filterwarnings('ignore')
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    
    print("\n--- Running Shareholder Increase Risk logic (Exit if > 80% stocks see increase) ---")
    port = Portfolio(10000000)
    strategy = ContrarianBreadthStrategy(dh, min_history_years=0.0)
    strategy.precompute_rsi(quarterly_dates)
    
    sim = SimEngine(dh, port, fee_model, tax_man)
    
    risk_off_active = False
    sh_increase_cache = {} # Cache to avoid redundant calls to get_shareholder_trend
    
    sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
    
    print("Starting simulation loop...")
    for today in sim_dates:
        # Determine "Current Quarter Code" for caching (optional but good for speed)
        month = today.month
        year = today.year
        if month >= 2 and month < 5: q_key = f"Dec-{year-1}"
        elif month >= 5 and month < 8: q_key = f"Mar-{year}"
        elif month >= 8 and month < 11: q_key = f"Jun-{year}"
        else: q_key = f"Sep-{year}"
        
        # 1. Technical Exits (Only if we have positions)
        if len(port.holdings) > 0:
            exits = strategy.check_exits(today, port.holdings)
            if exits:
                prices = dh.get_daily_prices(today)
                for isin in exits:
                    sim._sell_all(isin, today, prices)
                    
        # 2. Rebalance Check (This is the ONLY time we check the Risk-Off signal)
        if today in quarterly_dates:
            # Get Top 1000 Universe for breadth calculation
            univ = dh.get_universe(today, size=1000)
            univ_isins = univ['isin'].tolist()
            
            sh_trend = dh.get_shareholder_trend(today, lookback_quarters=4)
            if not sh_trend.empty:
                # Filter SH trend to ONLY Top 1000
                sh_trend_univ = sh_trend[sh_trend['isin'].isin(univ_isins)]
                if not sh_trend_univ.empty:
                    sh_increase_pct = (sh_trend_univ['decreased'] == 0).mean()
                else:
                    sh_increase_pct = 0.0
            else:
                sh_increase_pct = 0.0
            
            # Condition: If < 50% of Top 1000 see SH increase, remain in cash
            if sh_increase_pct < 0.50:
                print(f"REBALANCE RISK (Top 1000): SH Increase {sh_increase_pct:.1%} < 50% on {today.date()}. Moving to 100% Cash.")
                if len(port.holdings) > 0:
                    prices = dh.get_daily_prices(today)
                    for isin in list(port.holdings.keys()):
                        sim._sell_all(isin, today, prices)
            else:
                # Normal Rebalance
                new_target = strategy.calculate_selection(today)
                prices = dh.get_daily_prices(today)
                if prices:
                    sim._execute_rebalance(today, new_target, prices)
                    
        # 3. Daily NAV Log
        port.record_nav(today, dh.get_daily_prices(today))
        
    nav_df = pd.DataFrame(port.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print(f"SH INCREASE BREADTH RISK-OFF PERFORMANCE (2017 - 2026)")
    print("="*60)
    print(f"CAGR: {stats['CAGR']}")
    print(f"Sharpe Ratio: {stats['Sharpe Ratio']}")
    print(f"Max Drawdown: {stats['Max Drawdown']}")
    print("="*60)

if __name__ == "__main__":
    run_sh_increase_risk_research()
