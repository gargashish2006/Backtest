import requests
import re
import time
import json
import csv
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

class ScreenerSHPScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        self.target_quarters = ['Jun 2025', 'Sep 2025', 'Dec 2025']

    def scrape_company(self, code, retries=3):
        url = f"https://www.screener.in/company/{code}/"
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=12)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 10
                    print(f"  429 for {code}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                if response.status_code != 200:
                    print(f"Failed to fetch {code}: {response.status_code}")
                    return None
                
                content = response.text
                investors_match = re.search(r'<section[^>]+id="(?:investors|shareholding)"[^>]*>(.*?)</section>', content, re.DOTALL)
                if not investors_match:
                    print(f"No investors section for {code}")
                    return None
                
                section_html = investors_match.group(1)
                headers = re.findall(r'<th[^>]*>(.*?)</th>', section_html, re.DOTALL)
                headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]
                
                q_map = {}
                for target in self.target_quarters:
                    if target in headers:
                        q_map[target] = headers.index(target)
                
                if not q_map:
                    return None
                
                result = {q: {} for q in self.target_quarters}
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', section_html, re.DOTALL)
                for row in rows:
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                    cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                    if not cells: continue
                    label = cells[0].replace('&nbsp;+', '').strip()
                    for q, idx in q_map.items():
                        if idx < len(cells):
                            val_str = cells[idx].replace('%', '').replace(',', '').strip()
                            try:
                                val = float(val_str) if val_str and val_str != '--' else 0.0
                                if 'Promoter' in label: result[q]['promoter_pct'] = val
                                elif 'FII' in label: result[q]['fii_pct'] = val
                                elif 'DII' in label: result[q]['dii_pct'] = val
                                elif 'No. of Shareholders' in label: result[q]['total_shareholders'] = val
                            except ValueError: pass
                return result
                
            except Exception as e:
                print(f"Error scraping {code} (Attempt {attempt+1}): {e}")
                time.sleep(2)
        return None

    def run(self, input_json_files, max_workers=2):
        import concurrent.futures
        
        fix_file = REPO_ROOT / 'database/screener_shp_fixes.csv'
        existing_keys = set()
        if fix_file.exists():
            df_old = pd.read_csv(fix_file)
            for _, r in df_old.iterrows():
                existing_keys.add(f"{r['isin']}_{r['quarter']}")
        
        to_scrape = {} # code -> isin -> quarters
        for file_path in input_json_files:
            file_name = str(file_path)
            q_label = 'Dec 2025' if 'Dec_2025' in file_name else ('Sep 2025' if 'Sep_2025' in file_name else 'Jun 2025')
            with open(file_path) as f:
                data = json.load(f)
                for stock in data['stocks']:
                    code, isin = stock['bse_code'], stock['isin']
                    if f"{isin}_{q_label.replace(' ', '-')}" in existing_keys: continue
                    if code not in to_scrape: to_scrape[code] = {'isin': isin, 'quarters': []}
                    if q_label not in to_scrape[code]['quarters']: to_scrape[code]['quarters'].append(q_label)
        
        print(f"Total entries already scraped: {len(existing_keys)}")
        print(f"Total unique stocks left to scrape: {len(to_scrape)}")
        
        all_results = pd.read_csv(fix_file).to_dict('records') if fix_file.exists() else []
        count = 0
        
        def process_one(code):
            scraper_worker = ScreenerSHPScraper()
            shp_data = scraper_worker.scrape_company(code)
            res = []
            if shp_data:
                for q in to_scrape[code]['quarters']:
                    q_data = shp_data.get(q)
                    if q_data:
                        res.append({
                            'isin': to_scrape[code]['isin'],
                            'quarter': q.replace(' ', '-'),
                            'promoter_pct': q_data.get('promoter_pct', 0),
                            'fii_pct': q_data.get('fii_pct', 0),
                            'dii_pct': q_data.get('dii_pct', 0),
                            'total_shareholders': q_data.get('total_shareholders', 0)
                        })
            return res

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(process_one, code): code for code in to_scrape.keys()}
            for future in concurrent.futures.as_completed(future_to_code):
                count += 1
                try:
                    all_results.extend(future.result())
                except Exception as exc:
                    print(f"Stock {future_to_code[future]} failed: {exc}")
                
                if count % 20 == 0:
                    print(f"Progress: {count}/{len(to_scrape)}...")
                    self.save_results(all_results)
                
                time.sleep(1.5) # Jittered throttle

        self.save_results(all_results)
        print("Scraping complete.")

    def save_results(self, results):
        if not results:
            return
        df = pd.DataFrame(results)
        df.to_csv(REPO_ROOT / 'database/screener_shp_fixes.csv', index=False)

def apply_fixes():
    fix_file = REPO_ROOT / 'database/screener_shp_fixes.csv'
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
            if row['total_shareholders'] > 0:
                sh.loc[mask, 'total_shareholders'] = row['total_shareholders']
            updated_count += 1
        else:
            # Append new row
            name = isin_to_name.get(isin, "Unknown")
            new_rows.append({
                'isin': isin,
                'company_name': name,
                'quarter': q,
                'data_source': 'Screener',
                'total_shareholders': row['total_shareholders'],
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
    scraper = ScreenerSHPScraper()
    # If running with --apply, just apply existing fixes
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        apply_fixes()
    else:
        scraper.run([
            REPO_ROOT / 'database/bse_remaining_Jun_2025.json',
            REPO_ROOT / 'database/bse_remaining_Sep_2025.json',
            REPO_ROOT / 'database/bse_missing_Dec_2025.json'
        ])
        apply_fixes()
