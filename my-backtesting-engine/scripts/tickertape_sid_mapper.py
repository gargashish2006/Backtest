
import requests
import pandas as pd
import time
import os
import re

def get_tt_sid(symbol):
    """Search for a symbol on TickerTape and return its SID with retry on rate limit."""
    url = "https://api.tickertape.in/search"
    params = {
        'text': symbol,
        'types': 'stock',
        'pageNumber': 0
    }
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'accept-version': '7.9.0',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    while True:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data.get('message') == 'REQUEST_LIMIT_EXCEEDED':
                print(f"Rate limit hit at {symbol}. Sleeping 60s...")
                time.sleep(60)
                continue
                
            items = data.get('data', {}).get('items', [])
            
            # 1. Exact ticker match
            for item in items:
                if item.get('ticker') == symbol:
                    return item.get('sid'), item.get('slug')
            
            # 2. Relaxed match (symbol in slug)
            clean_sym = re.sub(r'[^A-Z0-9]', '', symbol).lower()
            for item in items:
                slug_parts = item.get('slug', '').split('-')
                if any(clean_sym == p.lower() for p in slug_parts):
                    return item.get('sid'), item.get('slug')
            
            # 3. First result if items exist
            if items:
                return items[0].get('sid'), items[0].get('slug')
            
            return None, None
            
        except Exception as e:
            print(f"Error searching for {symbol}: {e}")
            time.sleep(5)
            continue

def map_top_1000():
    # Load universe
    universe = pd.read_csv('database/screener_symbol_mapping.csv').head(1000)
    
    output_path = 'database/tickertape_symbol_mapping.csv'
    
    if os.path.exists(output_path):
        mapping_df = pd.read_csv(output_path)
        # Ensure we have all columns
        for col in ['isin', 'symbol', 'tt_sid', 'tt_slug']:
            if col not in mapping_df.columns:
                mapping_df[col] = None
    else:
        mapping_df = universe.copy()[['isin', 'symbol']]
        mapping_df['tt_sid'] = None
        mapping_df['tt_slug'] = None

    print(f"Total stocks to map: {len(mapping_df)}")
    
    for i, row in mapping_df.iterrows():
        # Only process if SID is missing
        if pd.notna(row['tt_sid']) and row['tt_sid'] != '':
            continue
            
        symbol = row['symbol']
        sid, slug = get_tt_sid(symbol)
        
        mapping_df.at[i, 'tt_sid'] = sid
        mapping_df.at[i, 'tt_slug'] = slug
        
        print(f"[{i+1}/1000] {symbol} -> SID: {sid}, Slug: {slug}")
        
        # Slower pace to avoid rate limits
        time.sleep(2.0)
        
        # Save every 20 for safety
        if (i + 1) % 20 == 0:
            mapping_df.to_csv(output_path, index=False)
            print(f"Saved mapping progress at {i+1}")

    mapping_df.to_csv(output_path, index=False)
    print("Mapping complete.")

if __name__ == "__main__":
    map_top_1000()
