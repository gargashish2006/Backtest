import sys
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

import pandas as pd
from data.data_handler import DataHandler

def generate_12q_breadth_report():
    print("Loading data...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    
    latest_date = pd.Timestamp("2026-02-05")
    
    print("Calculating 12Q (3-Year) Shareholder Trend...")
    sh_trend = dh.get_shareholder_trend(latest_date, lookback_quarters=12)
    
    if sh_trend.empty:
        print("No shareholder trend data available.")
        return
        
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    sh_trend['industry_group'] = sh_trend['isin'].map(dh.isin_to_group)
    
    # 1. Industry Level Calculation
    print("Processing Industry Level...")
    industry_stats = sh_trend.groupby('industry').agg(
        total_stocks=('decreased', 'count'),
        decreased_stocks=('decreased', 'sum')
    ).reset_index()
    
    industry_stats['breadth_pct'] = (industry_stats['decreased_stocks'] / industry_stats['total_stocks']) * 100
    industry_stats = industry_stats.sort_values('breadth_pct', ascending=False)
    
    # 2. Industry Group Level Calculation
    print("Processing Industry Group Level...")
    group_stats = sh_trend.groupby('industry_group').agg(
        total_stocks=('decreased', 'count'),
        decreased_stocks=('decreased', 'sum')
    ).reset_index()
    
    group_stats['breadth_pct'] = (group_stats['decreased_stocks'] / group_stats['total_stocks']) * 100
    group_stats = group_stats.sort_values('breadth_pct', ascending=False)
    
    # 3. Export to Excel
    output_path = repo_root / "12Q_Shareholder_Breadth_Report.xlsx"
    print(f"Exporting to {output_path}...")
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        industry_stats.to_excel(writer, sheet_name='Industry_Level_12Q', index=False)
        group_stats.to_excel(writer, sheet_name='Industry_Group_Level_12Q', index=False)
        
        # Add formatting
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            # Adjust column widths
            worksheet.column_dimensions['A'].width = 45
            worksheet.column_dimensions['B'].width = 15
            worksheet.column_dimensions['C'].width = 18
            worksheet.column_dimensions['D'].width = 15
            
    print("Done! Report successfully generated.")

if __name__ == "__main__":
    generate_12q_breadth_report()
