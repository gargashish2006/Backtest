
import pandas as pd
import numpy as np
import os

def clean_screener_date(date_str):
    if not isinstance(date_str, str): return None
    # Handle "Mar 2016\n            \n              9m"
    clean = date_str.split('\n')[0].strip()
    try:
        # Try mixed format parsing
        return pd.to_datetime(clean, format='mixed').strftime('%Y-%m-%d')
    except:
        return None

def consolidate():
    print("Loading datasets...")
    df_tt = pd.read_csv('database/tickertape_fundamentals.csv')
    df_sr = pd.read_csv('database/quarterly_fundamentals.csv')

    print(f"TickerTape records: {len(df_tt)}")
    print(f"Screener records: {len(df_sr)}")

    # 1. Clean Screener Dates
    print("Cleaning Screener dates...")
    df_sr['quarter_date'] = df_sr['quarter_date'].apply(clean_screener_date)
    df_sr = df_sr.dropna(subset=['quarter_date'])

    # 2. Rename columns to match
    df_sr = df_sr.rename(columns={'dividend_payout_ratio': 'dividend_payout_pct'})

    # 3. Handle duplicates
    # For a given (isin, quarter_date), prioritize TickerTape
    df_tt['source'] = 'tickertape'
    df_sr['source'] = 'screener'

    # Combine
    combined = pd.concat([df_tt, df_sr], ignore_index=True)
    
    # Sort by isin, date, and source (tickertape first)
    combined = combined.sort_values(by=['isin', 'quarter_date', 'source'], ascending=[True, True, False])
    
    # Drop duplicates by isin and date, keeping the first (tickertape due to sort)
    final = combined.drop_duplicates(subset=['isin', 'quarter_date'], keep='first')
    
    print(f"Consolidated records: {len(final)}")
    print(f"Unique ISINs: {final['isin'].nunique()}")
    
    # Remove source column for final save
    save_df = final.drop(columns=['source'])
    
    # Final cleanup: fill 0 for missing metrics where appropriate if we want, but let's keep NaNs
    
    save_df.to_csv('database/final_fundamentals.csv', index=False)
    save_df.to_parquet('database/final_fundamentals.parquet', index=False)
    print("Saved to database/final_fundamentals.parquet and .csv")

if __name__ == "__main__":
    if os.path.exists('database/tickertape_fundamentals.csv') and os.path.exists('database/quarterly_fundamentals.csv'):
        consolidate()
    else:
        print("Required files not found.")
