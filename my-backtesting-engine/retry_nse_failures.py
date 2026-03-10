#!/usr/bin/env python3
"""
Retry failed NSE stocks from nse_failures.csv
"""
import csv
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.data.shareholding_extractor import ShareholdingExtractor

def main():
    failures_file = 'nse_failures.csv'
    output_file = 'nse_shareholding_patterns.csv'
    retry_failures_file = 'nse_failures_retry.csv'
    
    # Read failed symbols
    failed_symbols = []
    with open(failures_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            failed_symbols.append(row['symbol'])
    
    print(f"Found {len(failed_symbols)} failed symbols to retry")
    
    # Initialize extractor
    extractor = ShareholdingExtractor(
        'dhan_instruments.csv',
        output_file,
        failures_csv_path=retry_failures_file
    )
    
    # Open output files in append mode
    success_count = 0
    still_failed_count = 0
    
    fieldnames = ['symbol', 'filing_date', 'submission_date', 'promoter_pct', 'public_pct', 'fii_pct', 'dii_pct', 'total_shareholders', 'total_shares']
    
    with open(output_file, 'a', newline='') as f, \
         open(retry_failures_file, 'w', newline='') as f_fail:
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        fail_writer = csv.DictWriter(f_fail, fieldnames=['symbol', 'reason'])
        fail_writer.writeheader()
        
        for idx, symbol in enumerate(failed_symbols, 1):
            print(f"Processing {symbol} ({idx}/{len(failed_symbols)})...")
            
            try:
                stock_results = extractor.process_stock(symbol)
                
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
                        'symbol': symbol,
                        'reason': 'No valid XBRL found or API error'
                    })
                    still_failed_count += 1
            
            except Exception as e:
                print(f"  ✗ Error: {e}")
                fail_writer.writerow({
                    'symbol': symbol,
                    'reason': f'Error: {str(e)}'
                })
                still_failed_count += 1
            
            # Batch checkpoint every 50
            if idx % 50 == 0:
                f.flush()
                os.fsync(f.fileno())
                f_fail.flush()
                os.fsync(f_fail.fileno())
                print(f"--- Checkpoint at {idx}/{len(failed_symbols)} ---")
    
    print(f"\n{'='*60}")
    print(f"NSE Retry Complete!")
    print(f"Successfully recovered: {success_count}")
    print(f"Still failed: {still_failed_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
