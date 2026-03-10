import csv
import time
import os
import sys
import argparse
import requests
from datetime import datetime
import re

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

from src.data.parsers.nse_shp_xbrl_parser import NSEShpXbrlParser
from src.data.parsers.bse_html_shp_parser import BSEHtmlShpParser

class BSEShareholdingExtractorSelenium:
    def __init__(self, symbols_csv_path, output_csv_path, failures_csv_path='bse_failures.csv', headless=True):
        self.symbols_csv_path = symbols_csv_path
        self.output_csv_path = output_csv_path
        self.failures_csv_path = failures_csv_path
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        # Basic session headers for XBRL download
        self.session.headers.update({
             'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def setup_driver(self):
        """Initialize Selenium WebDriver."""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
            
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # User Agent
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.driver.set_page_load_timeout(30)
    
    def restart_driver(self):
        """Explicitly restart the driver to free memory."""
        self.teardown_driver()
        time.sleep(1) # Cooldown
        self.setup_driver()

    def teardown_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def get_bse_codes(self):
        codes = []
        if not os.path.exists(self.symbols_csv_path):
            print(f"Error: File not found at {self.symbols_csv_path}")
            return []
        
        with open(self.symbols_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'BSE Code' in row:
                    code = row['BSE Code'].strip()
                    name = row.get('Name', '').strip()
                    if code:
                        codes.append({'code': code, 'name': name})
        return codes

    def get_filings_from_page(self, scrip_code):
        # Using the generic URL pattern
        # url = f"https://www.bseindia.com/stock-share-price/-/-/{scrip_code}/shareholding-pattern/"
        
        # This URL seems more reliable for redirection
        url = f"https://www.bseindia.com/stock-share-price/shp/scripcode/{scrip_code}/flag/7/"
        
        try:
            self.driver.get(url)
            # print(f"DEBUG: Loaded {self.driver.current_url}")
            
            # Wait for table with data
            try:
                # Wait for the specific data cells usually present in the table
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "tdcolumn"))
                )
            except:
                # Fallback to waiting for table if class not found
                try: 
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                except:
                    pass
            
            # Small buffer for rendering
            time.sleep(1) 
                
            html = self.driver.page_source
            # Save for debug if specific code run
            if scrip_code in ['532454', '500002']:
                 with open(f'bse_debug_{scrip_code}.html', 'w') as f:
                     f.write(html)
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all rows in all tables
            rows = soup.find_all('tr')
            filings = []
            
            for row in rows:
                # Common row structure: Period | .. | Link | .. | XBRL icon
                # We simply look for a link containing 'XBRL' or '.xml' or HTML link with XBRL text
                links = row.find_all('a')
                xbrl_link = None
                
                for a in links:
                    href = a.get('href', '')
                    text = a.get_text()
                    if 'XBRL' in text or '.xml' in href.lower():
                        xbrl_link = href
                        break
                
                if xbrl_link:
                    # Extract period cleaner
                    # Use regex to find "Month Year" or "DD Month Year" in the row text
                    # to avoid capturing headers or full table text.
                    row_text = row.get_text(" ", strip=True)
                    
                    # Pattern 1: Quarter Year (e.g. December 2025)
                    q_match = re.search(r'(March|June|September|December|Mar|Jun|Sep|Dec)[a-z]*\s+\d{4}', row_text, re.IGNORECASE)
                    
                    # Pattern 2: DD Month Year (e.g. 31 Mar 2025)
                    if not q_match:
                         q_match = re.search(r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}', row_text, re.IGNORECASE)
                    
                    if q_match:
                        period = q_match.group(0)
                    else:
                        # Fallback: existing logic but safe-guarded
                        cols = row.find_all('td')
                        period = cols[0].get_text().strip() if cols else "Unknown"
                        if len(period) > 100 or '\n' in period:
                            period = period.split('\n')[0][:50]
                            
                    # Refine link
                    if xbrl_link and not xbrl_link.startswith('http'):
                        xbrl_link = f"https://www.bseindia.com{xbrl_link}"

                    filings.append({
                        'Quarter': period,
                        'XBRL': xbrl_link
                    })
            
            return filings

        except Exception as e:
            print(f"Error checking {scrip_code}: {e}")
            return []

    def process_stock(self, stock_info):
        code = stock_info['code']
        name = stock_info['name']
        
        filings = self.get_filings_from_page(code)
        
        if not filings:
            return []

        results = []
        for filing in filings:
            xbrl_link = filing.get('XBRL')
            period = filing.get('Quarter')
            
            # Refine link
            if xbrl_link and not xbrl_link.startswith('http'):
                xbrl_link = f"https://www.bseindia.com{xbrl_link}"
                
            # Basic validation
            if not xbrl_link:
                continue
                
            is_html = '.html' in xbrl_link.lower()
            if not is_html and '.xml' not in xbrl_link.lower():
                continue

            result = {
                'symbol': code,
                'company_name': name,
                'period': period,
                'submission_date': None # Not easily available in simple table scan
            }
            
            # Download and parse
            try:
                # Use requests for the file download (usually faster/easier than selenium get + parsing page source)
                # However, BSE might block requests without cookies.
                # We can try to copy cookies from selenium.
                
                cookies = self.driver.get_cookies()
                req_cookies = {c['name']: c['value'] for c in cookies}
                
                x_resp = self.session.get(xbrl_link, cookies=req_cookies, timeout=15)
                
                # If needed verify status code, etc.
                if x_resp.status_code != 200:
                    x_resp = self.session.get(xbrl_link, timeout=15)
                
                if x_resp.status_code == 200:
                    parsed_data = None
                    if is_html:
                        parser = BSEHtmlShpParser(x_resp.text)
                        parsed_data = parser.parse()
                    else:
                        parser = NSEShpXbrlParser(x_resp.content)
                        parsed_data = parser.parse()
                        
                    if parsed_data:
                        result.update(parsed_data)
                        results.append(result)

            except Exception as e:
                # print(f"Error parsing XBRL for {code} {period}: {e}")
                pass
                
        return results

    def run(self, start_index=0, limit=None, batch_size=25):
        codes = self.get_bse_codes()
        print(f"Found {len(codes)} BSE codes.")
        
        self.setup_driver()
        
        try:
            end_index = start_index + limit if limit else len(codes)
            process_list = codes[start_index:end_index]
            print(f"Processing {len(process_list)} codes ({start_index} to {end_index})...")
            
            fieldnames = ['symbol', 'company_name', 'period', 'submission_date', 
                      'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 
                      'total_shareholders', 'total_shares']
                      
            mode = 'a' if start_index > 0 and os.path.exists(self.output_csv_path) else 'w'
            write_header = mode == 'w' or (mode == 'a' and os.path.getsize(self.output_csv_path) == 0)

            fail_mode = 'a' if start_index > 0 and os.path.exists(self.failures_csv_path) else 'w'
            write_fail_header = fail_mode == 'w' or (fail_mode == 'a' and os.path.getsize(self.failures_csv_path) == 0)

            with open(self.output_csv_path, mode, newline='') as f, \
                 open(self.failures_csv_path, fail_mode, newline='') as f_fail:
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                
                fail_writer = csv.DictWriter(f_fail, fieldnames=['symbol', 'company_name', 'reason'])
                if write_fail_header:
                    fail_writer.writeheader()
                
                count = 0
                for stock in process_list:
                    count += 1
                    print(f"Processing {stock['code']} ({count}/{len(process_list)})")
                    
                    stock_results = self.process_stock(stock)
                    if stock_results:
                        for res in stock_results:
                            writer.writerow(res)
                        # Only flush at batch interval to save time
                        print(f"  -> Buffered {len(stock_results)} records")
                    else:
                        print("  -> No valid XBRL found")
                        fail_writer.writerow({
                             'symbol': stock['code'],
                             'company_name': stock['name'],
                             'reason': 'No valid XBRL filings found or extraction failed'
                         })
                        
                    # Batch handling
                    if count % batch_size == 0:
                        f.flush()
                        os.fsync(f.fileno())
                        f_fail.flush()
                        os.fsync(f_fail.fileno())
                        print(f"--- Completed batch of {batch_size} (Total processed: {count}) ---")
                        print("Restarting driver for stability...")
                        self.restart_driver()
                    else:
                        pass # removed sleep to rely on explicit wait which is faster

        finally:
            self.teardown_driver()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--batch-size', type=int, default=25, help='Batch size for restart/save')
    parser.add_argument('--code', type=str, default=None, help='Specific BSE code to run')
    parser.add_argument('--head', action='store_true', help='Run in head mode (not headless)')
    args = parser.parse_args()

    extractor = BSEShareholdingExtractorSelenium(
        'bse_list.csv', 
        'bse_shareholding_patterns.csv',
        failures_csv_path='bse_failures.csv',
        headless=not args.head
    )
    
    if args.code:
        # Override process list to just this code
        codes = extractor.get_bse_codes()
        target = next((x for x in codes if x['code'] == args.code), None)
        if target:
            print(f"Targeting specific code: {target}")
            extractor.setup_driver()
            try:
                res = extractor.process_stock(target)
                print(f"Result count: {len(res)}")
                if res:
                    print(res[0])
            finally:
                extractor.teardown_driver()
        else:
            print(f"Code {args.code} not found in list")
    else:
        extractor.run(start_index=args.start, limit=args.limit, batch_size=args.batch_size)
