import csv
import time
import requests
import os
import sys
import argparse
from datetime import datetime

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# We will misuse the NSE parser if the XML structure is similar, 
# or build a generic one later. BSE XBRL is usually consistent with NSE.
from src.data.parsers.nse_shp_xbrl_parser import NSEShpXbrlParser

class BSEShareholdingExtractor:
    def __init__(self, symbols_csv_path, output_csv_path):
        self.symbols_csv_path = symbols_csv_path
        self.output_csv_path = output_csv_path
        self.session = requests.Session()
        
        # Headers mimicking a real browser interaction
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.bseindia.com/',
            'Origin': 'https://www.bseindia.com',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })
        self._initialize_cookies()

    def _initialize_cookies(self):
        try:
            # Visit homepage to get cookies
            self.session.get('https://www.bseindia.com', timeout=10)
        except Exception as e:
            print(f"Failed to initialize cookies: {e}")

    def get_bse_codes(self):
        codes = []
        if not os.path.exists(self.symbols_csv_path):
            print(f"Error: File not found at {self.symbols_csv_path}")
            return []
        
        with open(self.symbols_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Column B is 'BSE Code'
                if 'BSE Code' in row:
                    code = row['BSE Code'].strip()
                    name = row.get('Name', '').strip()
                    if code:
                        codes.append({'code': code, 'name': name})
        return codes

    def get_filings(self, scrip_code):
        # API requires clean headers
        url = f"https://api.bseindia.com/BseIndiaAPI/api/ShareholdingPattern/w?scripcode={scrip_code}&flag=7"
        
        # Reset headers to base state for API
        self.session.headers.update({
            'Referer': 'https://www.bseindia.com/',
            'Origin': 'https://www.bseindia.com'
        })
        
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and 'Table' in data:
                        return data['Table']
                    elif isinstance(data, list):
                        return data
                except:
                    # Parse HTML fallback
                    pass
            # Fallback: Try fetching the HTML page directly (SSR sometimes works)
            # url_html = f"https://www.bseindia.com/stock-share-price/shp/scripcode/{scrip_code}/flag/7/"
            # self.session.headers.update({'Referer': 'https://www.bseindia.com/'})
            # resp_html = self.session.get(url_html)
            # ... parsing logic ...
        except Exception as e:
            print(f"Error for {scrip_code}: {e}")
            
        return []

    def process_stock(self, stock_info):
        code = stock_info['code']
        name = stock_info['name']
        filings = self.get_filings(code)
        
        if not filings:
            return []

        results = []
        
        for filing in filings:
            # Inspect keys. Usually: 'qtrid', 'QtrName', 'XBRL_FILE' (or similar)
            # Based on inspection, keys might be:
            # - HOID (holding id?)
            # - T_Year (2025-2026)
            # - Quarter (December 2025)
            # - XBRL (link)
            
            # Note: The keys below are hypothetical based on common BSE API patterns.
            # We will print keys on first run to debug.
            
            # Actual keys from typical BSE SHP API:
            # FilngDate, Format, PUBLISH_DATE, Quarter, T_Year, XBRL
            
            xbrl_link = filing.get('XBRL')
            quarter = filing.get('Quarter', '')
            year = filing.get('T_Year', '')
            
            # Validate XBRL
            is_valid_xbrl = xbrl_link and 'null' not in xbrl_link.lower() and '.xml' in xbrl_link.lower()
            
            if not is_valid_xbrl:
                continue
                
            # Clean up XBRL link (BSE gives relative or absolute)
            # E.g. "http://www.bseindia.com/xml-data/..."
            if not xbrl_link.startswith('http'):
                xbrl_link = f"https://www.bseindia.com{xbrl_link}"
            
            result = {
                'symbol': code, # Using Code as symbol for BSE
                'company_name': name,
                'period': f"{quarter} {year}",
                'submission_date': filing.get('PUBLISH_DATE'),
            }
            
            try:
                # Download XBRL
                # print(f"Downloading XBRL: {xbrl_link}")
                x_resp = self.session.get(xbrl_link, timeout=15)
                if x_resp.status_code == 200:
                    parser = NSEShpXbrlParser(x_resp.content)
                    parsed_data = parser.parse()
                    if parsed_data:
                        result.update(parsed_data)
                        results.append(result)
            except Exception as e:
                pass # Skip bad files

        return results

    def run(self, start_index=0, limit=None, batch_size=25):
        codes = self.get_bse_codes()
        total = len(codes)
        print(f"Found {total} BSE codes.")
        
        end_index = start_index + limit if limit else total
        end_index = min(end_index, total)
        process_list = codes[start_index:end_index]
        print(f"Processing {len(process_list)} codes ({start_index} to {end_index}).")
        
        # Columns
        fieldnames = ['symbol', 'company_name', 'period', 'submission_date', 
                      'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 
                      'total_shareholders', 'total_shares']
                      
        mode = 'a' if start_index > 0 and os.path.exists(self.output_csv_path) else 'w'
        write_header = mode == 'w' or (mode == 'a' and os.path.getsize(self.output_csv_path) == 0)

        with open(self.output_csv_path, mode, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            
            count = 0
            for stock in process_list:
                count += 1
                if count % 10 == 0:
                    print(f"Processed {count}/{len(process_list)}...")
                
                stock_results = self.process_stock(stock)
                if stock_results:
                    for res in stock_results:
                        writer.writerow(res)
                    f.flush()
                
                time.sleep(0.1) # Be nice

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    extractor = BSEShareholdingExtractor('bse_list.csv', 'bse_shareholding_patterns.csv')
    extractor.run(start_index=args.start, limit=args.limit)
