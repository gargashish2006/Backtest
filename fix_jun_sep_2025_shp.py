#!/usr/bin/env python3
"""
Re-scrape shareholding pattern data from NSE for Jun-2025 and Sep-2025.
These quarters have broken ownership percentages (all zeros) for ~95% of BSE-sourced stocks.
"""
import csv
import time
import requests
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / 'my-backtesting-engine'))
from src.data.parsers.nse_shp_xbrl_parser import NSEShpXbrlParser

REPO_ROOT = Path(__file__).parent


class SHPRescraper:
    
    QUARTER_MAP = {
        'Jun-2025': '30-jun-2025',
        'Sep-2025': '30-sep-2025',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
        })
        self._refresh_nse()
    
    def _refresh_nse(self):
        try:
            self.session.get('https://www.nseindia.com', timeout=10)
            time.sleep(0.5)
        except: pass
    
    def get_nse_xbrl(self, symbol, quarter_key):
        nse_date = self.QUARTER_MAP[quarter_key]
        url = f'https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}'
        try:
            headers = {'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern'}
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                filings = resp.json()
                for f in filings:
                    period = f.get('date', '')
                    if nse_date in period.lower():
                        return f.get('xbrl')
            elif resp.status_code == 401:
                # Session expired, refresh
                self._refresh_nse()
                return self.get_nse_xbrl(symbol, quarter_key)
        except:
            pass
        return None
    
    def download_and_parse(self, xbrl_url):
        if not xbrl_url or 'null' in str(xbrl_url).lower():
            return None
        try:
            resp = self.session.get(xbrl_url, timeout=20)
            if resp.status_code == 200:
                parser = NSEShpXbrlParser(resp.content)
                return parser.parse()
        except:
            pass
        return None
    
    def get_broken_isins(self, quarter):
        sh = pd.read_csv(REPO_ROOT / 'database/shareholding_patterns.csv')
        q_data = sh[sh['quarter'] == quarter]
        broken = q_data[
            (q_data['promoter_holding_pct'] == 0) & 
            (q_data['fii_holding_pct'] == 0) & 
            (q_data['dii_holding_pct'] == 0) &
            (q_data['data_source'] == 'BSE')
        ]
        return broken['isin'].tolist()
    
    def run(self, quarter):
        broken_isins = self.get_broken_isins(quarter)
        mi = pd.read_csv(REPO_ROOT / 'database/master_identifiers.csv')
        mi_nse = mi[mi['nse_symbol'].notna()].set_index('isin')['nse_symbol'].to_dict()
        
        # Filter to broken ISINs that have NSE symbols
        scrape_list = [(isin, mi_nse[isin]) for isin in broken_isins if isin in mi_nse]
        
        print(f"\n{'='*60}")
        print(f"{quarter}: {len(broken_isins)} broken, {len(scrape_list)} have NSE symbols")
        print(f"{'='*60}")
        
        output_file = REPO_ROOT / f'database/shp_fix_{quarter.replace("-","_")}.csv'
        fieldnames = ['isin', 'symbol', 'quarter', 'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 
                      'total_shareholders', 'total_shares']
        
        found = 0
        failed = 0
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, (isin, symbol) in enumerate(scrape_list):
                xbrl_url = self.get_nse_xbrl(symbol, quarter)
                
                if xbrl_url:
                    data = self.download_and_parse(xbrl_url)
                    if data and (data.get('promoter_pct', 0) > 0 or data.get('public_pct', 0) > 0):
                        row = {'isin': isin, 'symbol': symbol, 'quarter': quarter}
                        row.update(data)
                        writer.writerow(row)
                        f.flush()
                        found += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                
                if (i+1) % 100 == 0:
                    print(f"  [{i+1}/{len(scrape_list)}] found={found}, failed={failed}")
                
                # Rate limit
                time.sleep(0.2)
                
                # Refresh NSE session every 150 requests
                if (i+1) % 150 == 0:
                    print(f"  Refreshing NSE session...")
                    self._refresh_nse()
                    time.sleep(2)
        
        print(f"\n✅ {quarter}: Scraped {found} successfully, {failed} failed")
        print(f"   Output: {output_file}")
        return output_file, found
    
    def apply_fixes(self, quarter, fix_file):
        fixes = pd.read_csv(fix_file)
        if len(fixes) == 0:
            print(f"No fixes to apply for {quarter}")
            return
        
        sh = pd.read_csv(REPO_ROOT / 'database/shareholding_patterns.csv')
        
        col_map = {
            'promoter_pct': 'promoter_holding_pct',
            'public_pct': 'public_holding_pct', 
            'fii_pct': 'fii_holding_pct',
            'dii_pct': 'dii_holding_pct',
        }
        
        fix_count = 0
        for _, fix_row in fixes.iterrows():
            mask = (sh['isin'] == fix_row['isin']) & (sh['quarter'] == quarter)
            if mask.sum() > 0:
                for src_col, dst_col in col_map.items():
                    val = fix_row.get(src_col, 0)
                    if pd.notna(val):
                        sh.loc[mask, dst_col] = round(float(val), 2)
                fix_count += 1
        
        sh.to_csv(REPO_ROOT / 'database/shareholding_patterns.csv', index=False)
        sh.to_parquet(REPO_ROOT / 'database/shareholding_patterns.parquet', index=False)
        print(f"✅ Applied {fix_count} fixes for {quarter}")


if __name__ == "__main__":
    scraper = SHPRescraper()
    
    for quarter in ['Jun-2025', 'Sep-2025']:
        fix_file, count = scraper.run(quarter)
        if count > 0:
            scraper.apply_fixes(quarter, fix_file)
    
    # Verify
    sh = pd.read_csv(REPO_ROOT / 'database/shareholding_patterns.csv')
    print(f"\n{'='*60}")
    print("VERIFICATION AFTER FIXES")
    print(f"{'='*60}")
    for q in ['Mar-2025', 'Jun-2025', 'Sep-2025', 'Dec-2025']:
        subset = sh[sh['quarter'] == q]
        all_zero = ((subset['promoter_holding_pct'] == 0) & 
                    (subset['fii_holding_pct'] == 0) & 
                    (subset['dii_holding_pct'] == 0)).sum()
        valid_prom = (subset['promoter_holding_pct'] > 0).sum()
        print(f"  {q}: {len(subset)} total, {valid_prom} valid promoter, {all_zero} all-zero")
