import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.slt15_strategy import SLT15Strategy

def extract_holdings_jan_2021():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    strategy = SLT15Strategy(dh)
    
    # Target Date: Jan 15, 2021
    target_date = pd.Timestamp("2021-01-15")
    
    # Identify rebalance dates that contribute to Jan 2021 portfolio
    # (8-quarter holding period means anything from Feb 2019 to Nov 2020)
    # But our backtest starts in May 2019.
    rebalance_years = [2019, 2020]
    rebalance_months = [2, 5, 8, 11]
    
    potential_dates = []
    for y in rebalance_years:
        for m in rebalance_months:
            d = pd.Timestamp(year=y, month=m, day=15)
            if pd.Timestamp("2019-05-15") <= d <= target_date:
                potential_dates.append(d)
                
    print(f"Reconstructing active tranches from: {[d.strftime('%Y-%m') for d in potential_dates]}\n")
    
    all_holdings = []
    
    for rb_date in potential_dates:
        # Get the actual trading date for rebalance
        all_trading_dates = dh.get_all_dates()
        actual_rb_date = min([d for d in all_trading_dates if d >= rb_date])
        
        selection = strategy.calculate_selection(actual_rb_date)
        if selection:
            for isin in selection.keys():
                all_holdings.append({
                    'Tranche Date': actual_rb_date.strftime('%Y-%m'),
                    'ISIN': isin,
                    'Company Name': dh.isin_to_name.get(isin, isin),
                    'Industry': dh.isin_to_industry.get(isin, "Unknown")
                })
                
    df_holdings = pd.DataFrame(all_holdings)
    
    # Sort and remove duplicates (though tranches are separate pots of money, 
    # the user asked for "holdings" which usually implies the unique list)
    print(f"SLT15 Holdings as of January 2021 (Full Staggered List):")
    print(df_holdings.sort_values(['Tranche Date', 'Industry']).to_string(index=False))
    
    # Summary of industry concentration
    print("\nIndustry Exposure Summary (Number of Stocks):")
    print(df_holdings['Industry'].value_counts())
    
    output_path = repo_root / "outputs/SLT15_Holdings_Jan2021.xlsx"
    df_holdings.to_excel(output_path, index=False)
    print(f"\nFull list saved to: {output_path}")

if __name__ == "__main__":
    extract_holdings_jan_2021()
