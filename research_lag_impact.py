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
from utils.analytics import calculate_metrics

def run_compare():
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # 1. Run No Lag (0 days)
    print("\nRunning Industry Momentum (Normal) with LAG = 0 DAYS...")
    p0 = Portfolio(10000000)
    f0 = FeeModel(0.0007, 0.001)
    t0 = TaxManager()
    s0 = IndustryMomentumStrategy(dh, lag_days=0)
    e0 = SimEngine(dh, p0, f0, t0)
    
    replan_dates = []
    for year in range(2017, 2026):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            all_dates = dh.get_all_dates()
            replan_dates.append(max([dt for dt in all_dates if dt <= d]))
            
    e0.run("2017-05-15", "2025-01-01", s0.calculate_selection, replan_dates)
    stats0 = calculate_metrics(pd.DataFrame(p0.nav_history))
    trades0 = pd.DataFrame(p0.trade_log)
    
    # 2. Run 1-Week Lag (7 days)
    print("\nRunning Industry Momentum (Normal) with LAG = 7 DAYS...")
    p7 = Portfolio(10000000)
    f7 = FeeModel(0.0007, 0.001)
    t7 = TaxManager()
    s7 = IndustryMomentumStrategy(dh, lag_days=7)
    e7 = SimEngine(dh, p7, f7, t7)
    e7.run("2017-05-15", "2025-01-01", s7.calculate_selection, replan_dates)
    stats7 = calculate_metrics(pd.DataFrame(p7.nav_history))
    trades7 = pd.DataFrame(p7.trade_log)
    
    # 3. Report Comparison
    print("\n" + "="*60)
    print(f"{'Metric':<20} | {'No Lag (0d)':<15} | {'1-Week Lag (7d)':<15}")
    print("-"*60)
    for k in ['Absolute Return', 'CAGR', 'Max Drawdown', 'Sharpe Ratio']:
        print(f"{k:<20} | {stats0[k]:<15} | {stats7[k]:<15}")
    print("="*60)
    
    # 4. Analyze Stock Contribution
    if not trades0.empty and not trades7.empty:
        perf0 = trades0.groupby('isin')['realized_gain'].sum().reset_index()
        perf7 = trades7.groupby('isin')['realized_gain'].sum().reset_index()
        perf0['name'] = perf0['isin'].map(dh.isin_to_name)
        perf7['name'] = perf7['isin'].map(dh.isin_to_name)
        
        comp = pd.merge(perf0, perf7, on=['isin', 'name'], suffixes=('_no_lag', '_7d_lag'))
        comp['diff'] = comp['realized_gain_7d_lag'] - comp['realized_gain_no_lag']
        
        print("\nSTOCKS THAT BENEFITED MOST FROM 1-WEEK LAG:")
        print(comp.sort_values('diff', ascending=False).head(10)[['name', 'realized_gain_no_lag', 'realized_gain_7d_lag', 'diff']])
        
        print("\nSTOCKS THAT WERE HURT MOST BY 1-WEEK LAG:")
        print(comp.sort_values('diff', ascending=True).head(10)[['name', 'realized_gain_no_lag', 'realized_gain_7d_lag', 'diff']])

if __name__ == "__main__":
    run_compare()
