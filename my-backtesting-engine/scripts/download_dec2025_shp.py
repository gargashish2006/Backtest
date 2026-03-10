#!/usr/bin/env python3.12
import csv
import time
import requests
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.parsers.nse_shp_xbrl_parser import NSEShpXbrlParser

class Dec2025SHPCollector:
    def __init__(self, input_csv, output_csv):
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
        })
        self.init_nse()
        self.init_bse()

    def init_nse(self):
        try:
            self.session.get('https://www.nseindia.com', timeout=10)
        except: pass

    def init_bse(self):
        try:
            self.session.get('https://www.bseindia.com', timeout=10)
        except: pass

    def get_nse_filing(self, symbol):
        url = f'https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}'
        try:
            # Add Referer for NSE
            headers = {'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern'}
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                filings = resp.json()
                for f in filings:
                    # Check for Dec 2025
                    period = f.get('date', '')
                    if '31-dec-2025' in period.lower():
                        return f.get('xbrl')
            return None
        except: return None

    def get_bse_filing(self, scrip_code):
        url = f"https://api.bseindia.com/BseIndiaAPI/api/ShareholdingPattern/w?scripcode={scrip_code}&flag=7"
        try:
            headers = {
                'Referer': 'https://www.bseindia.com/',
                'Origin': 'https://www.bseindia.com'
            }
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                filings = data.get('Table', []) if isinstance(data, dict) else data
                for f in filings:
                    # Key might be 'Quarter' or 'QtrName'
                    q = f.get('Quarter', f.get('QtrName', ''))
                    y = f.get('T_Year', '')
                    if 'December' in q and '2025' in str(y):
                        return f.get('XBRL')
            return None
        except: return None

    def download_and_parse(self, xbrl_url):
        if not xbrl_url or 'null' in xbrl_url.lower(): return None
        if not xbrl_url.startswith('http'):
            # Assume it's BSE if relative usually
            if '/xml-data/' in xbrl_url:
                xbrl_url = f"https://www.bseindia.com{xbrl_url}"
        
        try:
            resp = self.session.get(xbrl_url, timeout=20)
            if resp.status_code == 200:
                parser = NSEShpXbrlParser(resp.content)
                return parser.parse()
        except: return None

    def run(self):
        stocks = []
        with open(self.input_csv, 'r') as f:
            reader = csv.DictReader(f)
            stocks = list(reader)

        print(f"Total stocks to check: {len(stocks)}")
        
        fieldnames = ['isin', 'symbol', 'quarter', 'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 'total_shareholders', 'total_shares']
        
        with open(self.output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            found_count = 0
            for i, stock in enumerate(stocks):
                isin = stock['isin']
                nse_sym = stock.get('nse_symbol')
                bse_code = stock.get('bse_code')
                
                print(f"Checking {i+1}/{len(stocks)}: {isin} (NSE: {nse_sym}, BSE: {bse_code})...", end="\r")

                xbrl_url = None
                if nse_sym:
                    xbrl_url = self.get_nse_filing(nse_sym)
                
                if not xbrl_url and bse_code:
                    xbrl_url = self.get_bse_filing(bse_code)

                if xbrl_url:
                    print(f"[{i+1}/{len(stocks)}] Found Dec-25 XBRL for {isin} -> {xbrl_url}")
                    data = self.download_and_parse(xbrl_url)
                    if data:
                        res = {
                            'isin': isin,
                            'symbol': nse_sym if nse_sym else bse_code,
                            'quarter': 'Dec-2025',
                        }
                        res.update(data)
                        writer.writerow(res)
                        f.flush()
                        found_count += 1
                        print(f"  -> Extracted: {res['total_shareholders']} shareholders")
                    else:
                        print(f"  -> Parsing failed")
                else:
                    # print(f"[{i+1}/{len(stocks)}] No filing for {isin}")
                    pass
                
                time.sleep(0.1)
                
            print(f"\nDone! Found {found_count} new filings for Dec-2025.")

if __name__ == "__main__":
    collector = Dec2025SHPCollector(
        'database/stocks_missing_dec25_shareholding.csv',
        'database/shareholding_patterns_dec2025_new.csv'
    )
    collector.run()
