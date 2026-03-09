import sys
from pathlib import Path

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(repo_root))

import pandas as pd
from data.data_handler import DataHandler

def generate_combined_report():
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
    sh_trend['company_name'] = sh_trend['isin'].map(dh.isin_to_name)
    
    # Drop rows without industry info
    sh_trend = sh_trend.dropna(subset=['industry', 'industry_group'])

    # Get one example company for each industry (the largest by default, or just first)
    # We can use the first company name for simplicity
    example_companies = sh_trend.groupby('industry')['company_name'].first().reset_index()

    # Calculate Industry Breadth
    ind_stats = sh_trend.groupby(['industry', 'industry_group']).agg(
        total_stocks=('decreased', 'count'),
        decreased_stocks=('decreased', 'sum')
    ).reset_index()
    ind_stats['Industry 12Q Breadth %'] = (ind_stats['decreased_stocks'] / ind_stats['total_stocks']) * 100

    # Calculate Group Breadth
    group_stats = sh_trend.groupby('industry_group').agg(
        grp_total=('decreased', 'count'),
        grp_decreased=('decreased', 'sum')
    ).reset_index()
    group_stats['Industry Group 12Q Breadth %'] = (group_stats['grp_decreased'] / group_stats['grp_total']) * 100

    # Merge together
    combined = pd.merge(ind_stats, group_stats, on='industry_group', how='left')
    combined = pd.merge(combined, example_companies, on='industry', how='left')
    
    # Format output
    output_df = pd.DataFrame({
        'Industry Name': combined['industry'],
        'Industry Group': combined['industry_group'],
        'Number of Stocks': combined['total_stocks'],
        'Example Company': combined['company_name'],
        'Industry 12Q Breadth %': combined['Industry 12Q Breadth %'].round(2),
        'Industry Group 12Q Breadth %': combined['Industry Group 12Q Breadth %'].round(2)
    })
    
    # Sort by Industry Breadth
    output_df = output_df.sort_values('Industry 12Q Breadth %', ascending=False)
    
    output_path = repo_root / "12Q_Combined_Breadth_Report.xlsx"
    print(f"Exporting to {output_path}...")
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        output_df.to_excel(writer, sheet_name='Combined_12Q', index=False)
        worksheet = writer.sheets['Combined_12Q']
        worksheet.column_dimensions['A'].width = 40
        worksheet.column_dimensions['B'].width = 30
        worksheet.column_dimensions['C'].width = 18
        worksheet.column_dimensions['D'].width = 30
        worksheet.column_dimensions['E'].width = 25
        worksheet.column_dimensions['F'].width = 30
            
    print("Done! Report successfully generated.")

if __name__ == "__main__":
    generate_combined_report()
