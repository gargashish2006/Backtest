import json
import pandas as pd
import requests
import time
import re
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def get_tt_sid(query):
    url = "https://api.tickertape.in/search"
    params = {'text': query, 'types': 'stock', 'pageNumber': 0}
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'accept-version': '7.9.0',
        'User-Agent': 'Mozilla/5.0'
    }
    
    for _ in range(3):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            if data.get('message') == 'REQUEST_LIMIT_EXCEEDED':
                time.sleep(10)
                continue
            items = data.get('data', {}).get('items', [])
            if items:
                # Just take the first result's sid
                return items[0].get('sid'), items[0].get('slug')
            return None, None
        except Exception:
            time.sleep(2)
    return None, None

def main():
    # 1. Gather all ISINs to map
    files = [
        REPO_ROOT / 'database/fii_outliers.json'
    ]
    isins_to_map = set()
    for f in files:
        if f.exists():
            with open(f) as fp:
                data = json.load(fp)
                for stock in data['stocks']:
                    isins_to_map.add(stock['isin'])
    
    print(f"Found {len(isins_to_map)} unique ISINs to map.")
    
    # 2. Map ISIN -> Name using master_identifiers.csv
    mi_df = pd.read_csv(REPO_ROOT / 'database/master_identifiers.csv')
    isin_to_name = mi_df.set_index('isin')['company_name'].to_dict()
    isin_to_symbol = mi_df.set_index('isin')['nse_symbol'].to_dict()
    
    # 3. Load existing mapping
    map_file = REPO_ROOT / 'database/tickertape_symbol_mapping.csv'
    existing_isins = set()
    if map_file.exists():
        existing_df = pd.read_csv(map_file)
        existing_isins = set(existing_df['isin'].dropna())
    else:
        existing_df = pd.DataFrame(columns=['isin', 'symbol', 'tt_sid', 'tt_slug'])
    
    to_process = isins_to_map - existing_isins
    print(f"{len(existing_isins)} already mapped. {len(to_process)} left to map.")
    
    new_rows = []
    count = 0
    for isin in list(to_process):
        name = isin_to_name.get(isin, "")
        symbol = isin_to_symbol.get(isin, "")
        if pd.isna(symbol): symbol = ""
        
        query = symbol if symbol and str(symbol) != "nan" else name
        if not query:
            continue
            
        sid, slug = get_tt_sid(query)
        if not sid and symbol and name:
            # Try name if symbol failed
            sid, slug = get_tt_sid(name)
            
        new_rows.append({
            'isin': isin,
            'symbol': symbol,
            'tt_sid': sid,
            'tt_slug': slug
        })
        
        count += 1
        if count % 10 == 0:
            print(f"Mapped {count}/{len(to_process)}")
            pd.concat([existing_df, pd.DataFrame(new_rows)]).to_csv(map_file, index=False)
        
        time.sleep(0.5)
        
    pd.concat([existing_df, pd.DataFrame(new_rows)]).to_csv(map_file, index=False)
    print("Mapping complete.")

if __name__ == '__main__':
    main()
