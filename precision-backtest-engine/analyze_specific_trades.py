import pandas as pd
from pathlib import Path
import sys

# Add path for imports
sys.path.append("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.industry_momentum import IndustryMomentumStrategy

def analyze_specific_trades():
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Target Stocks
    target_names = ["Avalon Tech", "KIOCL", "Universal Cables"]
    name_to_isin = {v: k for k, v in dh.isin_to_name.items() if v in target_names}
    
    replan_dates = []
    for year in range(2017, 2026):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            all_dates = dh.get_all_dates()
            replan_dates.append(max([dt for dt in all_dates if dt <= d]))
            
    # Run No Lag
    p0 = Portfolio(10000000)
    s0 = IndustryMomentumStrategy(dh, lag_days=0)
    e0 = SimEngine(dh, p0, FeeModel(0,0), TaxManager())
    e0.run("2017-05-15", "2025-01-01", s0.calculate_selection, replan_dates)
    trades0 = pd.DataFrame(p0.trade_log)
    
    # Run 7d Lag
    p7 = Portfolio(10000000)
    s7 = IndustryMomentumStrategy(dh, lag_days=7)
    e7 = SimEngine(dh, p7, FeeModel(0,0), TaxManager())
    e7.run("2017-05-15", "2025-01-01", s7.calculate_selection, replan_dates)
    trades7 = pd.DataFrame(p7.trade_log)
    
    for name, isin in name_to_isin.items():
        print(f"\n{'='*40}")
        print(f"ANALYZING: {name} ({isin})")
        print(f"{'='*40}")
        
        t0 = trades0[trades0['isin'] == isin].copy()
        t7 = trades7[trades7['isin'] == isin].copy()
        
        print("\n[NO LAG TRADES]")
        if not t0.empty:
            print(t0[['date', 'type', 'price', 'qty', 'realized_gain']])
        else:
            print("No trades.")
            
        print("\n[7D LAG TRADES]")
        if not t7.empty:
            print(t7[['date', 'type', 'price', 'qty', 'realized_gain']])
        else:
            print("No trades.")

if __name__ == "__main__":
    analyze_specific_trades()
