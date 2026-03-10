import sys
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

import pandas as pd
from data.data_handler import DataHandler

def check_bpo_breadth():
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    
    latest_date = pd.Timestamp("2026-02-05")
    sh_trend = dh.get_shareholder_trend(latest_date, lookback_quarters=12)
    
    if sh_trend.empty:
        print("No shareholder trend data available.")
        return
        
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    sh_trend['name'] = sh_trend['isin'].map(dh.isin_to_name)
    
    bpo_stocks = sh_trend[sh_trend['industry'] == 'Business Process Outsourcing (BPO)/ Knowledge Process Outsourcing (KPO)']
    
    if bpo_stocks.empty:
        print("No BPO stocks found in the dataset with 12Q trend.")
        return
        
    total_bpo = len(bpo_stocks)
    decreased_bpo = bpo_stocks['decreased'].sum()
    breadth = (decreased_bpo / total_bpo) * 100 if total_bpo > 0 else 0
    
    print(f"BPO Industry 12Q Shareholder Decrease Breadth: {breadth:.2f}% ({decreased_bpo}/{total_bpo} stocks decreased)")
    print("\nStock breakdown:")
    print(bpo_stocks[['isin', 'name', 'curr_sh', 'prev_sh', 'decreased']].to_markdown(index=False))

if __name__ == "__main__":
    check_bpo_breadth()
