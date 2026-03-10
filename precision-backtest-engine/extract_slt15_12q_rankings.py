import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.slt15_strategy import SLT15Strategy

def extract_feb_2026_rankings():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    print("Loading DataHandler...")
    dh.load_data()
    
    # Needs universe size 1000, 12Q lookback
    slt15_12q = SLT15Strategy(dh, lookback_quarters=12)
    date = pd.Timestamp("2026-02-01")
    
    print(f"\nCalculating SLT15_12Q Whitelisted Industries for {date.date()}...")
    top_industries_breadth = slt15_12q.get_qualified_industries(date)
    
    sh_trend = dh.get_shareholder_trend(date, lookback_quarters=12)
    univ = dh.get_universe(date, size=1000)
    univ_isins = set(univ['isin'].tolist())

    stocks_info = []
    for _, row in sh_trend.iterrows():
        isin = row['isin']
        # Check if industry is whitelisted and if it's in Top 1000 market cap
        if isin in dh.isin_to_industry and dh.isin_to_industry[isin] in top_industries_breadth:
            if isin in univ_isins:
                sh_change = (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                
                # We need company name
                name = "Unknown"
                # Since dh.isin_to_name might not exist directly as a dictionary, let's fetch it:
                # the price data df might have TICKER or we can check what's available
                # Let's extract it from the raw metadata if available, otherwise just ISIN
                # We know the strategy selection relies on ISINs. Let's see if we can get the name from the price dataframe.
                rel_price_rows = dh.price_df[dh.price_df['isin'] == isin]
                if not rel_price_rows.empty and 'company_name' in rel_price_rows.columns:
                    name = rel_price_rows.iloc[0]['company_name']
                elif not rel_price_rows.empty and 'symbol' in rel_price_rows.columns:
                    name = rel_price_rows.iloc[0]['symbol']
                
                stocks_info.append({
                    'ISIN': isin,
                    'Company Name': name,
                    'Industry': dh.isin_to_industry[isin],
                    '12Q SH Change': sh_change
                })
                
    if not stocks_info:
        print("No stocks passed the filters.")
        return
        
    df = pd.DataFrame(stocks_info)
    # Master Global Ranking: Max Decrease First
    sorted_pool = df.sort_values('12Q SH Change', ascending=True)
    
    # Store raw values for Excel
    output_path = repo_root / "outputs/SLT15_12Q_Feb2026_Stock_Rankings.xlsx"
    sorted_pool.to_excel(output_path, index=False)
    
    # Format for terminal output
    sorted_pool['12Q SH Change'] = (sorted_pool['12Q SH Change'] * 100).round(2).astype(str) + '%'
    
    print("\n=== SLT15_12Q FEB 2026 MASTER STOCK RANKING (Pre-Selection) ===")
    print(f"Total Qualified Stocks (Top 1000 MCap + Whitelisted Industries): {len(sorted_pool)}\n")
    print(sorted_pool.to_string(index=False))
    print(f"\nSaved raw data to: {output_path}")

if __name__ == '__main__':
    extract_feb_2026_rankings()
