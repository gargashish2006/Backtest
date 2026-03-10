import time
import requests
import pandas as pd
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

class TickerTapeScraper:
    def __init__(self):
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'accept-version': '7.9.0',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.base_url = "https://api.tickertape.in"

    def fetch_data(self, sid, endpoint_type, horizon_or_growth='annual', view_type='normal', params={'count': 50}):
        url = f"{self.base_url}/stocks/financials/{endpoint_type}/{sid}/{horizon_or_growth}/{view_type}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
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

    def parse_date(self, date_str):
        if not date_str: return None
        return date_str.split('T')[0]

    def scrape_stock(self, isin, sid, symbol):
        try:
            # 1. Income Interim (Quarterly)
            q_income = self.fetch_data(sid, "income", "interim")
            
            # 2. Income Annual
            a_income = self.fetch_data(sid, "income", "annual")
            
            # 3. Balance Sheet Annual
            a_bs = self.fetch_data(sid, "balancesheet", "annual")
            
            consolidated = {}

            # Process Quarterly
            for q in q_income:
                date = self.parse_date(q.get('endDate'))
                if not date: continue
                
                if date not in consolidated:
                    consolidated[date] = {'isin': isin, 'symbol': symbol, 'quarter_date': date}
                
                consolidated[date].update({
                    'sales': q.get('qIncTrev'),
                    'operating_profit': q.get('qIncEbi'),
                    'opm_pct': round((q.get('qIncEbi') / q.get('qIncTrev') * 100), 2) if q.get('qIncTrev') and q.get('qIncEbi') else None
                })

            # Process Annual Income
            for a in a_income:
                date = self.parse_date(a.get('endDate'))
                if not date: continue
                
                if date not in consolidated:
                    consolidated[date] = {'isin': isin, 'symbol': symbol, 'quarter_date': date}
                
                consolidated[date].update({
                    'dividend_payout_pct': round(a.get('incPyr') * 100, 2) if a.get('incPyr') is not None else None
                })
                # Fill sales/profit if not already there from quarterly (Annual covers older years)
                if 'sales' not in consolidated[date] or consolidated[date]['sales'] is None:
                    consolidated[date].update({
                        'sales': a.get('incTrev'),
                        'operating_profit': a.get('incEbi'),
                        'opm_pct': round((a.get('incEbi') / a.get('incTrev') * 100), 2) if a.get('incTrev') and a.get('incEbi') else None
                    })

            # Process Annual BS
            for b in a_bs:
                date = self.parse_date(b.get('endDate'))
                if not date: continue
                
                if date not in consolidated:
                    consolidated[date] = {'isin': isin, 'symbol': symbol, 'quarter_date': date}
                    
                consolidated[date].update({
                    'borrowings': b.get('balTdeb'),
                    'cwip': b.get('balCwip')
                })

            return list(consolidated.values())
        except Exception as e:
            print(f"Error scraping {symbol}: {e}")
            return []

    def run(self, mapping_path='database/tickertape_symbol_mapping.csv', output_path='database/tickertape_fundamentals.csv'):
        if not os.path.exists(mapping_path):
            print("Mapping file not found. Run sid mapper first.")
            return

        df_map = pd.read_csv(mapping_path)
        # Only stocks with SIDs
        df_map = df_map[df_map['tt_sid'].notna()]
        
        all_data = []
        stocks = df_map.to_dict('records')
        total = len(stocks)
        
        print(f"Starting parallel scrape for {total} stocks with 5 workers...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_stock = {executor.submit(self.scrape_stock, s['isin'], s['tt_sid'], s['symbol']): s for s in stocks}
            
            count = 0
            for future in as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                except Exception as exc:
                    print(f"{stock['symbol']} generated an exception: {exc}")
                
                count += 1
                if count % 20 == 0:
                    print(f"[{count}/{total}] Completed. Total records: {len(all_data)}")
                    # Progressive save
                    pd.DataFrame(all_data).to_csv(output_path, index=False)
                    
        pd.DataFrame(all_data).to_csv(output_path, index=False)
        print(f"TickerTape Scrape Complete. Total records: {len(all_data)}")

if __name__ == "__main__":
    os.makedirs('database', exist_ok=True)
    scraper = TickerTapeScraper()
    scraper.run()
