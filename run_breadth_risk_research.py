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

def run_breadth_risk_research():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler and Breadth Cache...")
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
    
    # To be truly accurate, breadth is calculated only on the Top 1000 for that specific date
    print("Calculating True Top 1000 Breadth (200-DMA)...")
    
    sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
    breadth_records = {}
    # Optimization: pre-calculate MAs for the whole price_df once
    price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close')
    ma_200 = price_pivot.rolling(window=200).mean()
    
    # We only care about dates in our simulation range
    for dt in sim_dates:
        # Get Top 1000 ISINs for this date
        univ = dh.get_universe(dt, size=1000)
        if univ.empty: continue
        
        isins = univ['isin'].tolist()
        # Find how many of THESE 1000 isins are > 200-DMA
        p_slice = price_pivot.loc[dt, isins]
        m_slice = ma_200.loc[dt, isins]
        
        # Valid comparison (exclude NaNs from both sides)
        valid = (p_slice.notna() & m_slice.notna())
        if valid.any():
            above = (p_slice[valid] > m_slice[valid]).mean()
            breadth_records[dt] = above
            
    breadth_series = pd.Series(breadth_records)
    print(f"DEBUG: Max True Top 1000 Breadth: {breadth_series.max():.2%}")
    
    warnings.filterwarnings('ignore')
    fee_model = FeeModel(0.0015, 0.005)
    tax_man = TaxManager(0.20, 0.125)
    
    # --- Execute Backtest with Breadth Risk Logic ---
    print("\n--- Running Breadth Risk Variation (Exit > 80%) ---")
    port = Portfolio(10000000)
    strategy = ContrarianBreadthStrategy(dh, min_history_years=0.0)
    strategy.precompute_rsi(quarterly_dates)
    
    sim = SimEngine(dh, port, fee_model, tax_man)
    
    risk_off_active = False # State to stay in cash till next rebalance
    
    
    for today in sim_dates:
        # Get Breadth for today
        current_breadth = breadth_series.get(today, 0)
        
        # Check if we trigger Risk-Off (> 90%)
        if current_breadth > 0.90 and not risk_off_active:
            if len(port.holdings) > 0:
                print(f"BREADTH ALERT: {current_breadth:.1%} > 90% on {today.date()}. Exiting to cash.")
                prices = dh.get_daily_prices(today)
                for isin in list(port.holdings.keys()):
                    sim._sell_all(isin, today, prices)
            risk_off_active = True
            
        # 1. Check Technical Exits (Only if Risk-Off is not active)
        if not risk_off_active:
             exits = strategy.check_exits(today, port.holdings)
             if exits:
                 prices = dh.get_daily_prices(today)
                 for isin in exits:
                     sim._sell_all(isin, today, prices)
            
        # 2. Check Rebalance
        if today in quarterly_dates:
            # RESET Risk-Off state on rebalance day
            # But check if rebalance itself is allowed
            if current_breadth > 0.90:
                print(f"REBALANCE SKIPPED: Breadth {current_breadth:.1%} still > 90% on {today.date()}.")
                risk_off_active = True # Stay in cash
            else:
                risk_off_active = False # Re-enable trading
                new_target = strategy.calculate_selection(today)
                prices = dh.get_daily_prices(today)
                if prices:
                    sim._execute_rebalance(today, new_target, prices)
            
        # 3. Daily NAV Log
        port.record_nav(today, dh.get_daily_prices(today))
        
    nav_df = pd.DataFrame(port.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print(f"MARKET BREADTH RISK-OFF PERFORMANCE (2017 - 2026)")
    print("="*60)
    print(f"CAGR: {stats['CAGR']}")
    print(f"Sharpe Ratio: {stats['Sharpe Ratio']}")
    print(f"Max Drawdown: {stats['Max Drawdown']}")
    print("="*60)

if __name__ == "__main__":
    run_breadth_risk_research()
