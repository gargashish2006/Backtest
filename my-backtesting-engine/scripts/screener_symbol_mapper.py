#!/usr/bin/env python
"""
Screener.in Symbol Mapper

Maps our ISINs/symbols to Screener.in company slugs.
Screener.in uses NSE symbols as URL slugs.
"""

import pandas as pd
from pathlib import Path
import re

def clean_symbol_for_screener(symbol: str) -> str:
    """
    Clean and normalize symbol for Screener.in URL.
    
    Screener.in uses uppercase NSE symbols with some special handling:
    - Remove spaces and special characters
    - Keep alphanumeric and hyphens
    - Uppercase
    """
    if pd.isna(symbol):
        return None
    
    # Remove common suffixes
    symbol = str(symbol).strip()
    
    # Screener uses uppercase
    symbol = symbol.upper()
    
    # Remove special characters except hyphen and ampersand
    symbol = re.sub(r'[^A-Z0-9\-&]', '', symbol)
    
    return symbol if symbol else None


def create_symbol_mapping(price_data_path: str, industry_info_path: str, output_path: str) -> pd.DataFrame:
    """
    Create mapping from ISIN to Screener.in slug.
    
    Returns DataFrame with columns: isin, symbol, screener_slug, company_name, market_cap_rank
    """
    print("Loading price data...")
    price_df = pd.read_parquet(price_data_path)
    industry_df = pd.read_parquet(industry_info_path)
    
    # Get latest price data for market cap ranking
    latest_prices = price_df.sort_values('date').groupby('isin').last().reset_index()
    
    # Load shares outstanding for market cap calculation
    shares_path = Path(price_data_path).parent / 'outstanding_shares.csv'
    if shares_path.exists():
        shares_df = pd.read_csv(shares_path)
        shares_map = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
        latest_prices['shares'] = latest_prices['isin'].map(shares_map)
        latest_prices['market_cap'] = latest_prices['close'] * latest_prices['shares']
    else:
        # Fallback to shareholding patterns parquet
        shp_path = Path(price_data_path).parent / 'shareholding_patterns.parquet'
        if shp_path.exists():
            shp_df = pd.read_parquet(shp_path)
            latest_shp = shp_df.sort_values('quarter').groupby('isin').last()
            shares_map = latest_shp['total_outstanding_shares'].to_dict()
            latest_prices['shares'] = latest_prices['isin'].map(shares_map)
            latest_prices['market_cap'] = latest_prices['close'] * latest_prices['shares']
        else:
            # Fallback: use close price as proxy
            latest_prices['market_cap'] = latest_prices['close']
    
    # Rank by market cap
    latest_prices = latest_prices.dropna(subset=['market_cap'])
    latest_prices = latest_prices.sort_values('market_cap', ascending=False)
    latest_prices['market_cap_rank'] = range(1, len(latest_prices) + 1)
    
    # Get unique symbols per ISIN (prefer NSE)
    symbol_df = price_df[price_df['exchange'] == 'NSE'].groupby('isin')['symbol'].first().reset_index()
    
    # For ISINs without NSE symbol, use any available
    missing_isins = set(latest_prices['isin']) - set(symbol_df['isin'])
    other_symbols = price_df[price_df['isin'].isin(missing_isins)].groupby('isin')['symbol'].first().reset_index()
    symbol_df = pd.concat([symbol_df, other_symbols], ignore_index=True).drop_duplicates(subset='isin')
    
    # Create mapping DataFrame
    mapping = latest_prices[['isin', 'market_cap_rank', 'market_cap']].merge(
        symbol_df, on='isin', how='left'
    ).merge(
        industry_df[['isin', 'company_name']], on='isin', how='left'
    )
    
    # Create Screener.in slug
    mapping['screener_slug'] = mapping['symbol'].apply(clean_symbol_for_screener)
    
    # Sort by market cap rank
    mapping = mapping.sort_values('market_cap_rank').reset_index(drop=True)
    
    # Save mapping
    mapping.to_csv(output_path, index=False)
    print(f"✓ Saved symbol mapping: {output_path}")
    print(f"  Total stocks: {len(mapping)}")
    print(f"  With valid slugs: {mapping['screener_slug'].notna().sum()}")
    
    return mapping


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    
    mapping = create_symbol_mapping(
        price_data_path=str(project_root / 'database' / 'price_data.parquet'),
        industry_info_path=str(project_root / 'database' / 'industry_info.parquet'),
        output_path=str(project_root / 'database' / 'screener_symbol_mapping.csv')
    )
    
    print("\nTop 20 stocks by market cap:")
    print(mapping[['market_cap_rank', 'symbol', 'screener_slug', 'company_name']].head(20).to_string(index=False))
