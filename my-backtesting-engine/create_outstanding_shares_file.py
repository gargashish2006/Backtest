"""
Create a file with latest outstanding shares for each stock.
Uses Dec-25 data if available, otherwise Sep-25, then earlier quarters.
"""

import pandas as pd
import numpy as np
from datetime import datetime

def extract_outstanding_shares():
    """Extract latest outstanding shares for each stock"""
    
    print("Loading shareholding patterns...")
    shp = pd.read_parquet('database/shareholding_patterns.parquet')
    
    print(f"Total shareholding records: {len(shp):,}")
    print(f"Columns: {shp.columns.tolist()}")
    
    # Use the correct column: total_outstanding_shares
    # Not total_shareholders (which is the number of shareholders, not shares)
    total_shares_col = 'total_outstanding_shares'
    
    if total_shares_col not in shp.columns:
        print(f"\nError: '{total_shares_col}' column not found")
        print("Please check the shareholding_patterns.csv file structure")
        return None
    
    print(f"Using column: '{total_shares_col}' for outstanding shares")
    
    # Convert quarter to sortable format
    shp['quarter_date'] = pd.to_datetime(shp['quarter'], format='%b-%Y', errors='coerce')
    
    # Sort by isin and quarter (most recent first)
    shp = shp.sort_values(['isin', 'quarter_date'], ascending=[True, False])
    
    # Get latest outstanding shares for each stock
    latest_shares = []
    
    print("\nExtracting latest data per stock...")
    for isin, group in shp.groupby('isin'):
        # Try to get Dec-25 first
        dec_25 = group[group['quarter'] == 'Dec-2025']
        
        if not dec_25.empty and pd.notna(dec_25.iloc[0][total_shares_col]):
            record = dec_25.iloc[0]
        else:
            # Try Sep-25
            sep_25 = group[group['quarter'] == 'Sep-2025']
            if not sep_25.empty and pd.notna(sep_25.iloc[0][total_shares_col]):
                record = sep_25.iloc[0]
            else:
                # Get most recent with valid data
                valid_records = group[pd.notna(group[total_shares_col])]
                if not valid_records.empty:
                    record = valid_records.iloc[0]
                else:
                    # No valid outstanding shares data
                    continue
        
        latest_shares.append({
            'isin': record['isin'],
            'company_name': record['company_name'],
            'total_outstanding_shares': record[total_shares_col],
            'data_quarter': record['quarter'],
            'data_date': record['quarter_date'].strftime('%Y-%m-%d') if pd.notna(record['quarter_date']) else None,
            'data_source': record.get('data_source', 'Unknown')
        })
    
    # Create DataFrame
    df = pd.DataFrame(latest_shares)
    
    # Sort by company name
    df = df.sort_values('company_name')
    
    print(f"\nExtracted outstanding shares for {len(df):,} stocks")
    
    # Quarter distribution
    print("\nData quarter distribution:")
    quarter_dist = df['data_quarter'].value_counts().head(10)
    for quarter, count in quarter_dist.items():
        print(f"  {quarter}: {count:,} stocks ({count/len(df)*100:.1f}%)")
    
    return df

def add_market_identifiers(shares_df):
    """Add exchange symbols and codes for convenience"""
    
    print("\nAdding market identifiers...")
    master = pd.read_parquet('database/master_identifiers.parquet')
    
    # Merge with master identifiers
    df = shares_df.merge(
        master[['isin', 'nse_symbol', 'bse_code', 'primary_exchange', 'primary_symbol']],
        on='isin',
        how='left'
    )
    
    # Reorder columns
    df = df[[
        'isin',
        'company_name',
        'nse_symbol',
        'bse_code',
        'primary_exchange',
        'primary_symbol',
        'total_outstanding_shares',
        'data_quarter',
        'data_date',
        'data_source'
    ]]
    
    return df

def calculate_sample_market_caps(shares_df):
    """Calculate market cap for a few stocks as example"""
    
    print("\nCalculating sample market caps (using latest closing prices)...")
    
    # Load price data (last record for each stock)
    price = pd.read_parquet('database/price_data.parquet')
    price['date'] = pd.to_datetime(price['date'])
    
    # Get latest date
    latest_date = price['date'].max()
    print(f"Latest price date: {latest_date.date()}")
    
    recent_prices = price[price['date'] >= latest_date - pd.Timedelta(days=30)]
    
    # Get most recent price for each stock
    latest_prices = recent_prices.sort_values('date').groupby('isin').tail(1)
    latest_prices = latest_prices[['isin', 'date', 'close']].rename(columns={'close': 'latest_price'})
    
    # Merge with shares
    sample = shares_df.merge(latest_prices, on='isin', how='inner').head(20)
    
    # Calculate market cap
    sample['market_cap_inr'] = sample['total_outstanding_shares'] * sample['latest_price']
    sample['market_cap_cr'] = sample['market_cap_inr'] / 10000000  # Convert to crores
    
    print(f"\nSample Market Capitalizations (as of {latest_date.date()}):")
    print("-" * 100)
    
    for _, row in sample.iterrows():
        print(f"{row['company_name'][:40]:40} | "
              f"Price: ₹{row['latest_price']:8.2f} | "
              f"Shares: {row['total_outstanding_shares']/1e7:8.2f}Cr | "
              f"Market Cap: ₹{row['market_cap_cr']:10,.2f}Cr")
    
    return sample

def main():
    print("="*80)
    print("Creating Outstanding Shares File")
    print("="*80)
    print()
    
    # Extract outstanding shares
    shares_df = extract_outstanding_shares()
    
    if shares_df is None or shares_df.empty:
        print("\nNo data extracted. Exiting.")
        return
    
    # Add market identifiers
    shares_df = add_market_identifiers(shares_df)
    
    # Save to file
    output_file = 'database/outstanding_shares.csv'
    shares_df.to_csv(output_file, index=False)
    
    print(f"\n✅ File saved: {output_file}")
    print(f"   Records: {len(shares_df):,}")
    file_size = len(shares_df) * 100 / 1024  # Approximate
    print(f"   Size: ~{file_size:.2f} KB")
    
    # Calculate some sample market caps
    calculate_sample_market_caps(shares_df)
    
    # Create summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    print(f"\nTotal stocks with outstanding shares data: {len(shares_df):,}")
    
    # Shares distribution
    print("\nOutstanding shares distribution:")
    print(f"  Min: {shares_df['total_outstanding_shares'].min()/1e7:.2f} Cr shares")
    print(f"  Median: {shares_df['total_outstanding_shares'].median()/1e7:.2f} Cr shares")
    print(f"  Mean: {shares_df['total_outstanding_shares'].mean()/1e7:.2f} Cr shares")
    print(f"  Max: {shares_df['total_outstanding_shares'].max()/1e7:.2f} Cr shares")
    
    # Exchange distribution
    print("\nExchange distribution:")
    exchange_dist = shares_df['primary_exchange'].value_counts()
    for exchange, count in exchange_dist.items():
        print(f"  {exchange}: {count:,} stocks ({count/len(shares_df)*100:.1f}%)")
    
    print("\n" + "="*80)
    print("✅ Complete! You can now calculate market cap for any date.")
    print("="*80)
    print("\nUsage:")
    print("  market_cap = price * outstanding_shares")
    print("  Example: ₹1,250 × 6,339,375,974 shares = ₹7,924 billion market cap")

if __name__ == "__main__":
    main()
