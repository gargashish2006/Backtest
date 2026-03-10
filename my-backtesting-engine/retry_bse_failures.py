#!/usr/bin/env python3
"""
Retry failed BSE stocks from bse_failures.csv
"""
import csv
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.data.bse_shareholding_extractor_selenium import BSEShareholdingExtractorSelenium

def main():
    failures_file = 'bse_failures.csv'
    output_file = 'bse_shareholding_patterns.csv'
    retry_failures_file = 'bse_failures_retry.csv'
    
    # Read failed stocks
    failed_stocks = []
    with open(failures_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            failed_stocks.append({
                'code': row['symbol'],
                'name': row['company_name']
            })
    
    print(f"Found {len(failed_stocks)} failed stocks to retry")
    
    # Initialize extractor
    extractor = BSEShareholdingExtractorSelenium(
        'bse_list.csv',
        output_file,
        failures_csv_path=retry_failures_file,
        headless=True
    )
    
    extractor.setup_driver()
    
    # Open output files in append mode
    success_count = 0
    still_failed_count = 0
    
    try:
        with open(output_file, 'a', newline='') as f, \
             open(retry_failures_file, 'w', newline='') as f_fail:
            
            writer = csv.DictWriter(f, fieldnames=[
                'symbol', 'company_name', 'period', 'submission_date',
                'total_shares', 'total_shareholders',
                'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct'
            ])
            
            fail_writer = csv.DictWriter(f_fail, fieldnames=['symbol', 'company_name', 'reason'])
            fail_writer.writeheader()
            
            for idx, stock in enumerate(failed_stocks, 1):
                print(f"Processing {stock['code']} ({idx}/{len(failed_stocks)})...")
                
                try:
                    stock_results = extractor.process_stock(stock)
                    
                    if stock_results:
                        for res in stock_results:
                            writer.writerow(res)
                        f.flush()
                        os.fsync(f.fileno())
                        print(f"  ✓ Extracted {len(stock_results)} records")
                        success_count += 1
                    else:
                        print("  ✗ Still no valid XBRL found")
                        fail_writer.writerow({
                            'symbol': stock['code'],
                            'company_name': stock['name'],
                            'reason': 'No valid XBRL filings found or extraction failed'
                        })
                        still_failed_count += 1
                
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    fail_writer.writerow({
                        'symbol': stock['code'],
                        'company_name': stock['name'],
                        'reason': f'Error: {str(e)}'
                    })
                    still_failed_count += 1
                
                # Restart driver every 10 stocks
                if idx % 10 == 0:
                    print("Restarting driver for stability...")
                    extractor.restart_driver()
    
    finally:
        extractor.teardown_driver()
    
    print(f"\n{'='*60}")
    print(f"Retry Complete!")
    print(f"Successfully recovered: {success_count}")
    print(f"Still failed: {still_failed_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
