import time
import requests
import pandas as pd
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent

class TickerTapeSHPScraper:
    def __init__(self):
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'accept-version': '7.9.0',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.base_url = "https://api.tickertape.in"

    def fetch_data(self, sid):
        url = f"{self.base_url}/stocks/holdings/{sid}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.ok:
                return response.json().get('data', [])
            else:
                if response.status_code == 429:
                    print(f"Rate limited for {sid}. Sleeping 5s...")
                    time.sleep(5)
                else:
                    print(f"Error {response.status_code} for {url}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        return []

    def map_date_to_quarter(self, date_str):
        if not date_str: return None
        dt = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
        q = (dt.month - 1) // 3 + 1
        q_to_month = {1: "Mar", 2: "Jun", 3: "Sep", 4: "Dec"}
        return f"{q_to_month[q]}-{dt.year}"

    def scrape_stock(self, isin, sid):
        try:
            data = self.fetch_data(sid)
            results = []
            for entry in data:
                q_label = self.map_date_to_quarter(entry.get('date'))
                if q_label:
                    metrics = entry.get('data', {})
                    if 'fiPctT' in metrics or 'pmPctT' in metrics:
                        results.append({
                            'isin': isin,
                            'quarter': q_label,
                            'promoter_pct': metrics.get('pmPctT', 0),
                            'fii_pct': metrics.get('fiPctT', 0),
                            'dii_pct': metrics.get('diPctT', 0),
                        })
            return results
        except Exception as e:
            print(f"Error scraping {sid}: {e}")
            return []

    def run(self, input_json_files, max_workers=5):
        mapping_path = REPO_ROOT / 'database/tickertape_symbol_mapping.csv'
        if not mapping_path.exists():
            print("Mapping file not found.")
            return

        df_map = pd.read_csv(mapping_path)
        df_map = df_map[df_map['tt_sid'].notna()]
        isin_to_sid = df_map.set_index('isin')['tt_sid'].to_dict()
        
        to_scrape = {} # sid -> isin
        for file_path in input_json_files:
            file_name = str(file_path)
            with open(file_path) as f:
                data = json.load(f)
                for stock in data['stocks']:
                    isin = stock['isin']
                    sid = isin_to_sid.get(isin)
                    if sid:
                        to_scrape[sid] = isin
        
        print(f"Total unique stocks to scrape from Tickertape API: {len(to_scrape)}")
        
        all_results = []
        total = len(to_scrape)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sid = {executor.submit(self.scrape_stock, isin, sid): sid for sid, isin in to_scrape.items()}
            
            count = 0
            for future in as_completed(future_to_sid):
                sid = future_to_sid[future]
                try:
                    data = future.result()
                    if data:
                        all_results.extend(data)
                except Exception as exc:
                    print(f"{sid} generated an exception: {exc}")
                
                count += 1
                if count % 20 == 0:
                    print(f"[{count}/{total}] Completed. Total records: {len(all_results)}")
                
                time.sleep(0.5)
                    
        self.save_results(all_results)
        print(f"TickerTape Scrape Complete. Total records: {len(all_results)}")

    def save_results(self, results):
        if not results:
            return
        df = pd.DataFrame(results)
        df.to_csv(REPO_ROOT / 'database/tickertape_shp_fixes.csv', index=False)

def apply_fixes():
    fix_file = REPO_ROOT / 'database/tickertape_shp_fixes.csv'
    if not fix_file.exists():
        print("No fix file found.")
        return
    
    fixes = pd.read_csv(fix_file)
    sh_file = REPO_ROOT / 'database/shareholding_patterns.csv'
    sh = pd.read_csv(sh_file)
    
    # Load master identifiers for name mapping
    mi_file = REPO_ROOT / 'database/master_identifiers.csv'
    mi = pd.read_csv(mi_file)
    isin_to_name = mi.set_index('isin')['company_name'].to_dict()

    updated_count = 0
    added_count = 0
    
    new_rows = []

    for _, row in fixes.iterrows():
        isin = row['isin']
        q = row['quarter']
        mask = (sh['isin'] == isin) & (sh['quarter'] == q)
        
        if mask.any():
            sh.loc[mask, 'promoter_holding_pct'] = row['promoter_pct']
            sh.loc[mask, 'public_holding_pct'] = 100 - row['promoter_pct']
            sh.loc[mask, 'fii_holding_pct'] = row['fii_pct']
            sh.loc[mask, 'dii_holding_pct'] = row['dii_pct']
            updated_count += 1
        else:
            # Append new row
            name = isin_to_name.get(isin, "Unknown")
            new_rows.append({
                'isin': isin,
                'company_name': name,
                'quarter': q,
                'data_source': 'TickertapeAPI',
                'total_shareholders': 0,
                'total_outstanding_shares': 0.0,
                'promoter_holding_pct': row['promoter_pct'],
                'public_holding_pct': 100 - row['promoter_pct'],
                'fii_holding_pct': row['fii_pct'],
                'dii_holding_pct': row['dii_pct']
            })
            added_count += 1
            
    if new_rows:
        sh = pd.concat([sh, pd.DataFrame(new_rows)], ignore_index=True)

    sh.to_csv(sh_file, index=False)
    sh.to_parquet(sh_file.with_suffix('.parquet'), index=False)
    print(f"Updated {updated_count} rows and added {added_count} new rows in shareholding database.")

if __name__ == "__main__":
    import sys
    scraper = TickerTapeSHPScraper()
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        apply_fixes()
    else:
        scraper.run([
            REPO_ROOT / 'database/fii_outliers.json'
        ], max_workers=5)
        apply_fixes()
