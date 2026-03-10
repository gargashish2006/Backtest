#!/usr/bin/env python
"""
Screener.in Fundamental Scraper (Optimized for Top 1000)

Collects and consolidates quarterly fundamental data from Screener.in.
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from pathlib import Path
import random
import os
from datetime import datetime

class ScreenerScraper:
    def __init__(self, session=None):
        self.base_url = "https://www.screener.in"
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        })
    
    def parse_date(self, date_str):
        """Standardize date strings to YYYY-MM-DD"""
        if not date_str or pd.isna(date_str):
            return date_str
        
        date_str = date_str.strip()
        
        # Possible formats: "Dec 2022", "Mar 2024", "Sep-23", "Mar 2024", "TTM"
        if date_str.upper() == "TTM":
            return "TTM"
            
        import calendar
        
        formats = [
            "%b %Y",    # Dec 2022
            "%b-%y",    # Sep-23
            "%B %Y",    # December 2022
            "%b %y",    # Dec 22
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                last_day = calendar.monthrange(dt.year, dt.month)[1]
                return dt.replace(day=last_day).strftime("%Y-%m-%d")
            except:
                continue
        
        return date_str

    def fetch_page(self, slug):
        url = f"{self.base_url}/company/{slug}/consolidated/"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 404:
                url = f"{self.base_url}/company/{slug}/"
                response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return None
            return response.text
        except Exception as e:
            print(f"Error fetching {slug}: {e}")
            return None

    def parse_table(self, soup, table_id):
        table_section = soup.find('section', id=table_id)
        if not table_section:
            return None
        
        table = table_section.find('table', class_='data-table')
        if not table:
            return None
        
        thead = table.find('thead')
        if not thead: return None
        headers = [th.text.strip() for th in thead.find_all('th') if th.text.strip()]
        
        tbody = table.find('tbody')
        if not tbody: return None
        
        rows = []
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if not tds: continue
            
            metric_col = tds[0]
            metric_name = metric_col.text.strip()
            if metric_col.find('button'):
                metric_name = metric_col.find('button').text.strip()
            
            values = []
            for td in tds[1:]:
                val = td.text.strip().replace(',', '').replace('%', '')
                try:
                    values.append(float(val))
                except ValueError:
                    values.append(None)
            
            rows.append({'metric': metric_name, 'values': values})
            
        return {'headers': headers, 'rows': rows}

    def scrape_stock(self, isin, slug):
        html = self.fetch_page(slug)
        if not html: return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        sources = {
            'quarters': self.parse_table(soup, 'quarters'),
            'balance_sheet': self.parse_table(soup, 'balance-sheet'),
            'profit-loss': self.parse_table(soup, 'profit-loss')
        }
        
        raw_rows = []
        for source_name, table_data in sources.items():
            if not table_data: continue
            
            dates = table_data['headers']
            rows = table_data['rows']
            
            for i, date_str in enumerate(dates):
                std_date = self.parse_date(date_str)
                row_data = {
                    'isin': isin,
                    'quarter_date': std_date,
                }
                
                found_metric = False
                for row in rows:
                    metric = row['metric'].lower()
                    val = row['values'][i] if i < len(row['values']) else None
                    if val is None: continue
                    
                    if source_name == 'quarters':
                        if any(x in metric for x in ['sales', 'revenue', 'interest income']):
                            if 'growth' not in metric and 'net' not in metric:
                                row_data['sales'] = val; found_metric = True
                        elif any(x in metric for x in ['operating profit', 'financing profit']):
                            if 'margin' not in metric:
                                row_data['operating_profit'] = val; found_metric = True
                        elif any(x in metric for x in ['opm', 'financing margin']):
                            row_data['opm_pct'] = val; found_metric = True
                    
                    elif source_name == 'balance_sheet':
                        if 'borrowings' in metric:
                            row_data['borrowings'] = val; found_metric = True
                        elif 'cwip' in metric or 'capital work in progress' in metric:
                            row_data['cwip'] = val; found_metric = True
                    
                    elif source_name == 'profit-loss':
                        if 'dividend payout' in metric:
                            row_data['dividend_payout_pct'] = val; found_metric = True
                
                if found_metric:
                    raw_rows.append(row_data)
        
        if not raw_rows: return None
        
        # Consolidate metrics for same date
        df = pd.DataFrame(raw_rows)
        consolidated = df.groupby(['isin', 'quarter_date']).first().reset_index()
        return consolidated.to_dict('records')

def run_full_scrape(limit=1000):
    mapping_path = 'database/screener_symbol_mapping.csv'
    output_path = 'database/quarterly_fundamentals.csv'
    
    if not os.path.exists(mapping_path):
        print("Mapping file not found!")
        return
    
    mapping = pd.read_csv(mapping_path)
    mapping = mapping.head(limit)
    
    scraped_isins = set()
    if os.path.exists(output_path):
        existing_df = pd.read_csv(output_path)
        scraped_isins = set(existing_df['isin'].unique())
        print(f"Resuming scrape. Already scraped: {len(scraped_isins)}")
    
    scraper = ScreenerScraper()
    all_results = []
    
    try:
        count = 0
        for _, row in mapping.iterrows():
            isin = row['isin']
            slug = row['screener_slug']
            
            if isin in scraped_isins: continue
            if pd.isna(slug): continue
            
            stock_data = scraper.scrape_stock(isin, slug)
            if stock_data:
                all_results.extend(stock_data)
                count += 1
                print(f"[{count}] Scraped {row['symbol']} ({isin})")
            
            # Rate limiting: 2-4 seconds
            time.sleep(random.uniform(2, 4))
            
            # Save every 20 stocks
            if count > 0 and count % 20 == 0:
                print(f"Saving progress... ({count} new stocks)")
                new_df = pd.DataFrame(all_results)
                if os.path.exists(output_path):
                    existing_df = pd.read_csv(output_path)
                    final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['isin', 'quarter_date'])
                    final_df.to_csv(output_path, index=False)
                else:
                    new_df.to_csv(output_path, index=False)
                all_results = [] # Clear memory
                
    except KeyboardInterrupt:
        print("Scrape interrupted by user. Saving current Progress...")
    finally:
        if all_results:
            new_df = pd.DataFrame(all_results)
            if os.path.exists(output_path):
                existing_df = pd.read_csv(output_path)
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['isin', 'quarter_date'])
                final_df.to_csv(output_path, index=False)
            else:
                new_df.to_csv(output_path, index=False)
            print("Final progress saved.")

if __name__ == "__main__":
    # For initial testing, let's just do Top 10
    # run_full_scrape(limit=10)
    
    # Or start the Top 1000 batch
    run_full_scrape(limit=1000)
