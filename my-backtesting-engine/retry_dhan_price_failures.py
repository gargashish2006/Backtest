#!/usr/bin/env python3
"""
Retry failed stocks from the Dhan price download.

This script identifies stocks that failed in the first run and retries them
with slower rate limits to avoid 429 errors.
"""

import pandas as pd
import csv
import sys
import argparse

def get_failed_stocks(instruments_csv='dhan_instruments.csv', 
                     downloaded_csv='daily_price_data_full.csv'):
    """
    Identify stocks that failed to download.
    
    Returns:
        List of symbols that need to be retried
    """
    # Load all NSE equity instruments
    all_instruments = pd.read_csv(instruments_csv)
    all_symbols = set(all_instruments[
        (all_instruments['exchange_segment'] == 'NSE_EQ') & 
        (all_instruments['instrument'] == 'EQUITY')
    ]['symbol'].values)
    
    print(f"Total NSE equity stocks: {len(all_symbols)}")
    
    # Load successfully downloaded symbols
    if downloaded_csv:
        downloaded_data = pd.read_csv(downloaded_csv)
        downloaded_symbols = set(downloaded_data['symbol'].unique())
        print(f"Successfully downloaded: {len(downloaded_symbols)}")
    else:
        downloaded_symbols = set()
    
    # Find failed symbols
    failed_symbols = all_symbols - downloaded_symbols
    print(f"Failed/Missing: {len(failed_symbols)}")
    
    return sorted(list(failed_symbols))


def create_failed_instruments_csv(failed_symbols, 
                                  instruments_csv='dhan_instruments.csv',
                                  output_csv='dhan_failed_instruments.csv'):
    """
    Create a new instruments CSV with only the failed stocks.
    """
    # Load original instruments
    instruments = pd.read_csv(instruments_csv)
    
    # Filter to failed symbols
    failed_instruments = instruments[
        instruments['symbol'].isin(failed_symbols)
    ]
    
    # Save to new CSV
    failed_instruments.to_csv(output_csv, index=False)
    print(f"Created {output_csv} with {len(failed_instruments)} failed stocks")
    
    return output_csv


def main():
    parser = argparse.ArgumentParser(description='Identify and prepare retry for failed Dhan downloads')
    parser.add_argument('--instruments', type=str, default='dhan_instruments.csv', 
                       help='Original instruments CSV')
    parser.add_argument('--downloaded', type=str, default='daily_price_data_full.csv',
                       help='Downloaded price data CSV')
    parser.add_argument('--output', type=str, default='dhan_failed_instruments.csv',
                       help='Output CSV with failed instruments')
    
    args = parser.parse_args()
    
    # Get failed symbols
    failed_symbols = get_failed_stocks(args.instruments, args.downloaded)
    
    if not failed_symbols:
        print("\n✓ All stocks downloaded successfully!")
        return
    
    # Create failed instruments CSV
    failed_csv = create_failed_instruments_csv(
        failed_symbols, 
        args.instruments, 
        args.output
    )
    
    print(f"\n{'='*70}")
    print("Next Steps:")
    print(f"{'='*70}")
    print(f"1. Run the retry with slower rate limits:")
    print(f"\n   python src/data/dhan_price_downloader.py \\")
    print(f"       --client-id YOUR_CLIENT_ID \\")
    print(f"       --access-token YOUR_ACCESS_TOKEN \\")
    print(f"       --workers 1 \\")
    print(f"       --output daily_price_data_retry.csv")
    print(f"\n   (Update dhan_instruments.csv to {failed_csv} temporarily,")
    print(f"    or modify the script to accept --instruments parameter)")
    print(f"\n2. Merge the retry data with the main file")


if __name__ == "__main__":
    main()
