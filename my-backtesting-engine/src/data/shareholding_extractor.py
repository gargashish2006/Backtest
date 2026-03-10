import csv
import time
import requests
import os
import sys
import argparse
from datetime import datetime

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.data.parsers.nse_shp_xbrl_parser import NSEShpXbrlParser

class ShareholdingExtractor:
    def __init__(self, symbols_csv_path, output_csv_path, failures_csv_path='nse_failures.csv'):
        self.symbols_csv_path = symbols_csv_path
        self.output_csv_path = output_csv_path
        self.failures_csv_path = failures_csv_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern'
        })
        self._initialize_cookies()

    def _initialize_cookies(self):
        try:
            # Visit homepage to get cookies
            resp = self.session.get('https://www.nseindia.com', timeout=10)
            # Also visit the shareholding pattern page to ensure we have all necessary cookies
            if resp.status_code == 200:
                time.sleep(0.5)
                self.session.get('https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern', timeout=10)
        except Exception as e:
            print(f"Failed to initialize cookies: {e}")

    def get_symbols(self):
        symbols = []
        if not os.path.exists(self.symbols_csv_path):
            print(f"Error: Symbols file not found at {self.symbols_csv_path}")
            return []
        
        with open(self.symbols_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter for NSE Equity if columns exist
                if row.get('exchange_segment') == 'NSE_EQ' and row.get('instrument') == 'EQUITY':
                    symbols.append(row['symbol'])
        return symbols

    def get_filings(self, symbol, retry_count=3):
        url = f'https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}'
        
        for attempt in range(retry_count):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    return data
                elif resp.status_code == 401 or resp.status_code == 403:
                    # Cookie expired, reinitialize
                    print(f"  Session expired for {symbol}, reinitializing cookies...")
                    self._initialize_cookies()
                    time.sleep(1)
                    continue
                elif resp.status_code == 404:
                    # No data for this symbol
                    return []
                else:
                    # Other error, maybe retry
                    if attempt < retry_count - 1:
                        time.sleep(1)
                        continue
            except requests.exceptions.Timeout:
                print(f"  Timeout for {symbol}, attempt {attempt + 1}/{retry_count}")
                if attempt < retry_count - 1:
                    time.sleep(2)
                    continue
            except Exception as e:
                print(f"  Error fetching filings for {symbol}: {e}")
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
        
        return []

    def process_stock(self, symbol):
        filings = self.get_filings(symbol)
        if not filings:
            return []

        results = []
        # sort filings just in case, though usually sorted by date desc
        
        for filing in filings:
            xbrl_url = filing.get('xbrl')
            filing_date = filing.get('date')
            submission_date = filing.get('submissionDate') or filing.get('broadcastDate')

            # Check if XBRL is valid (exists and is not a placeholder)
            is_xbrl_valid = xbrl_url and 'null' not in xbrl_url and xbrl_url != '-' and not xbrl_url.endswith('/-')

            # Base result structure
            result = {
                'symbol': symbol,
                'filing_date': filing_date,
                'submission_date': submission_date
            }

            if is_xbrl_valid:
                # Download XBRL
                try:
                    # print(f"Downloading XBRL for {symbol} ({filing_date}) from {xbrl_url}")
                    xbrl_resp = self.session.get(xbrl_url, timeout=20)
                    if xbrl_resp.status_code != 200:
                        print(f"Failed download {xbrl_url}: {xbrl_resp.status_code}")
                    else:
                        parser = NSEShpXbrlParser(xbrl_resp.content)
                        parsed_data = parser.parse()
                        result.update(parsed_data)
                        
                        # Only append if we successfully parsed the XBRL
                        if parsed_data:
                            results.append(result)
                            
                except Exception as e:
                    print(f"Error parsing {symbol} for {filing_date}: {e}")
            
            # Note: We are deliberately skipping records where XBRL is missing or invalid
            # to ensure only full detailed data is saved.
            
            # Reduced sleep for faster execution
            if is_xbrl_valid:
                time.sleep(0.05)
                
        return results

    def run(self, output_file, start_index=0, limit=None, batch_size=None):
        symbols = self.get_symbols()
        total_symbols = len(symbols)
        print(f"Found {total_symbols} symbols.")
        
        # Calculate process range
        end_index = start_index + limit if limit else total_symbols
        end_index = min(end_index, total_symbols)
        symbols_to_process = symbols[start_index:end_index]
        
        print(f"Processing range: {start_index} to {end_index} (Count: {len(symbols_to_process)})")
        if batch_size:
            print(f"Running in batches of {batch_size}")
        
        fieldnames = ['symbol', 'filing_date', 'submission_date', 'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 'total_shareholders', 'total_shares']
        
        # Determining mode: 'a' (append) if starting > 0 and file exists, else 'w'
        mode = 'a' if start_index > 0 and os.path.exists(output_file) else 'w'
        write_header = mode == 'w' or (mode == 'a' and os.path.getsize(output_file) == 0)

        fail_mode = 'a' if start_index > 0 and os.path.exists(self.failures_csv_path) else 'w'
        write_fail_header = fail_mode == 'w' or (fail_mode == 'a' and os.path.getsize(self.failures_csv_path) == 0)

        with open(output_file, mode, newline='') as f, \
             open(self.failures_csv_path, fail_mode, newline='') as f_fail:
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            
            fail_writer = csv.DictWriter(f_fail, fieldnames=['symbol', 'reason'])
            if write_fail_header:
                fail_writer.writeheader()
            
            count = 0
            for sym in symbols_to_process:
                global_index = start_index + count + 1
                print(f"Processing {sym} ({global_index}/{total_symbols})...")
                stock_results = self.process_stock(sym)
                
                if stock_results:
                    for res in stock_results:
                        writer.writerow(res)
                    f.flush() # Ensure it's written
                else:
                    fail_writer.writerow({'symbol': sym, 'reason': 'No valid XBRL found or API error'})
                    f_fail.flush()
                
                count += 1
                
                # Batch logic: extra sleep or logging
                if batch_size and count % batch_size == 0:
                    f.flush()
                    os.fsync(f.fileno())
                    f_fail.flush()
                    os.fsync(f_fail.fileno())
                    print(f"--- Completed batch of {batch_size} (Total processed: {count}) - Data Saved ---")
                    print("Cooling down for 1 second...")
                    time.sleep(1)
                else:
                    time.sleep(0.2) # Reduced rate limit per stock for faster execution

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract NSE Shareholding Patterns')
    parser.add_argument('--start', type=int, default=0, help='Start index of symbols')
    parser.add_argument('--limit', type=int, default=None, help='Total number of symbols to process in this run')
    parser.add_argument('--batch-size', type=int, default=25, help='Batch size for logging and cooldown')
    args = parser.parse_args()

    extractor = ShareholdingExtractor(
        symbols_csv_path='dhan_instruments.csv',
        output_csv_path='nse_shareholding_patterns.csv',
        failures_csv_path='nse_failures.csv'
    )
    # Run based on CLI args
    extractor.run('nse_shareholding_patterns.csv', start_index=args.start, limit=args.limit, batch_size=args.batch_size)
