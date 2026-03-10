#!/usr/bin/env python3
"""
Download monthly candle data from Dhan API for NSE equity stocks.

This script downloads historical monthly OHLCV data for stocks to be used
in backtesting strategies.
"""

import os
import sys
import csv
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))


class DhanPriceDataDownloader:
    def __init__(self, client_id, access_token):
        """
        Initialize Dhan API client.
        
        Args:
            client_id: Dhan API client ID
            access_token: Dhan API access token
        """
        self.base_url = "https://api.dhan.co"
        self.client_id = client_id
        self.access_token = access_token
        self.session = requests.Session()
        self.lock = threading.Lock()  # For thread-safe operations
        
        self.session.headers.update({
            'client-id': client_id,
            'access-token': access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_historical_data(self, security_id, exchange_segment, interval='1MON', 
                           from_date=None, to_date=None):
        """
        Get historical candle data from Dhan API.
        
        Args:
            security_id: Dhan security ID
            exchange_segment: Exchange segment (e.g., 'NSE_EQ')
            interval: Candle interval ('1MON' for monthly)
            from_date: Start date (datetime object)
            to_date: End date (datetime object)
        
        Returns:
            List of candle data dictionaries
        """
        # Default date range: last 10 years
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(days=3650)  # ~10 years
        
        # Format dates as YYYY-MM-DD
        from_date_str = from_date.strftime('%Y-%m-%d')
        to_date_str = to_date.strftime('%Y-%m-%d')
        
        # Dhan historical data endpoint
        url = f"{self.base_url}/v2/charts/historical"
        
        payload = {
            "securityId": security_id,  # Keep as string or int
            "exchangeSegment": exchange_segment,
            "instrument": "EQUITY",
            "expiryCode": 0,
            "fromDate": from_date_str,
            "toDate": to_date_str
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Dhan API returns data in columnar format
                if isinstance(data, dict) and all(k in data for k in ['open', 'high', 'low', 'close', 'timestamp']):
                    # Convert columnar format to list of candles
                    candles = []
                    timestamps = data.get('timestamp', [])
                    opens = data.get('open', [])
                    highs = data.get('high', [])
                    lows = data.get('low', [])
                    closes = data.get('close', [])
                    volumes = data.get('volume', [])
                    
                    for i in range(len(timestamps)):
                        candles.append({
                            'timestamp': timestamps[i],
                            'open': opens[i],
                            'high': highs[i],
                            'low': lows[i],
                            'close': closes[i],
                            'volume': volumes[i] if i < len(volumes) else 0
                        })
                    return candles
                
                # Legacy format handling
                elif isinstance(data, dict):
                    if 'data' in data and data['data']:
                        return data['data']
                    elif 'candles' in data and data['candles']:
                        return data['candles']
                elif isinstance(data, list):
                    return data
                
                return []
            else:
                print(f"  Error: Status {response.status_code} - {response.text[:200]}")
                return []
                
        except requests.exceptions.Timeout:
            print("  Error: Request timeout")
            return []
        except Exception as e:
            print(f"  Error: {e}")
            return []
    
    def download_single_stock(self, instrument, global_idx, total):
        """
        Download data for a single stock (thread-safe).
        
        Args:
            instrument: Dictionary with symbol, security_id, exchange_segment
            global_idx: Global index for progress tracking
            total: Total number of stocks
        
        Returns:
            Tuple of (success, records_list, symbol, candle_count)
        """
        symbol = instrument['symbol']
        security_id = instrument['security_id']
        exchange_segment = instrument['exchange_segment']
        
        try:
            # Add small delay to respect rate limits
            time.sleep(1.0)  # 1 second delay for retry (extra conservative)
            
            # Download data
            candles = self.get_historical_data(
                security_id=security_id,
                exchange_segment=exchange_segment,
                interval='1MON'
            )
            
            if candles:
                records = []
                for candle in candles:
                    # Handle both dictionary and array formats
                    if isinstance(candle, dict):
                        timestamp = candle.get('timestamp')
                        date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                        
                        record = {
                            'symbol': symbol,
                            'security_id': security_id,
                            'date': date,
                            'open': candle.get('open'),
                            'high': candle.get('high'),
                            'low': candle.get('low'),
                            'close': candle.get('close'),
                            'volume': candle.get('volume', 0)
                        }
                    else:
                        # Legacy array format
                        if len(candle) >= 6:
                            timestamp = candle[0]
                            date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                            
                            record = {
                                'symbol': symbol,
                                'security_id': security_id,
                                'date': date,
                                'open': candle[1],
                                'high': candle[2],
                                'low': candle[3],
                                'close': candle[4],
                                'volume': candle[5]
                            }
                        else:
                            continue
                    records.append(record)
                
                return (True, records, symbol, len(candles))
            else:
                return (False, [], symbol, 0)
        except Exception as e:
            return (False, [], symbol, 0)
    
    def download_all_stocks(self, instruments_csv='dhan_instruments.csv', 
                           output_csv='monthly_price_data.csv',
                           start_index=0, limit=None, batch_size=50, 
                           max_workers=10):
        """
        Download daily candle data for all equity stocks (parallel).
        Supports both NSE_EQ and BSE_EQ exchange segments.
        
        Args:
            instruments_csv: Path to Dhan instruments CSV
            output_csv: Output CSV file path
            start_index: Start index in instruments list
            limit: Limit number of stocks to process
            batch_size: Number of stocks per batch checkpoint
            max_workers: Number of parallel download threads (default: 10)
        """
        print(f"Loading instruments from {instruments_csv}...")
        
        # Load instruments
        instruments = []
        with open(instruments_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support both NSE_EQ and BSE_EQ
                if row['exchange_segment'] in ['NSE_EQ', 'BSE_EQ'] and row['instrument'] == 'EQUITY':
                    instruments.append({
                        'symbol': row['symbol'],
                        'security_id': row['security_id'],
                        'exchange_segment': row['exchange_segment']
                    })
        
        total = len(instruments)
        print(f"Found {total} equity instruments")
        
        # Calculate range
        end_index = start_index + limit if limit else total
        end_index = min(end_index, total)
        instruments_to_process = instruments[start_index:end_index]
        
        print(f"Processing {len(instruments_to_process)} stocks (index {start_index} to {end_index})")
        print(f"Using {max_workers} parallel workers")
        
        # Prepare output file
        mode = 'a' if start_index > 0 and os.path.exists(output_csv) else 'w'
        write_header = mode == 'w' or (mode == 'a' and os.path.getsize(output_csv) == 0)
        
        fieldnames = [
            'symbol', 'security_id', 'date', 'open', 'high', 'low', 'close', 'volume'
        ]
        
        success_count = 0
        failure_count = 0
        total_records = 0
        batch_records = []
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_instrument = {
                executor.submit(self.download_single_stock, instrument, start_index + idx, total): 
                (idx, instrument) for idx, instrument in enumerate(instruments_to_process, 1)
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_instrument):
                idx, instrument = future_to_instrument[future]
                global_idx = start_index + idx
                
                try:
                    success, records, symbol, candle_count = future.result()
                    
                    if success:
                        batch_records.extend(records)
                        total_records += len(records)
                        success_count += 1
                        print(f"[{global_idx}/{total}] {symbol}: ✓ {candle_count} candles")
                    else:
                        failure_count += 1
                        print(f"[{global_idx}/{total}] {symbol}: ✗ No data")
                    
                    # Write batch to file
                    if len(batch_records) >= batch_size * 100:  # Accumulate ~100 records per stock
                        with self.lock:
                            with open(output_csv, mode, newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                if write_header:
                                    writer.writeheader()
                                    write_header = False
                                    mode = 'a'
                                
                                writer.writerows(batch_records)
                                f.flush()
                                os.fsync(f.fileno())
                        
                        print(f"--- Checkpoint: {success_count} stocks, {total_records} records, {failure_count} failed ---")
                        batch_records = []
                
                except Exception as e:
                    print(f"[{global_idx}/{total}] {instrument['symbol']}: ✗ Error - {e}")
                    failure_count += 1
        
        # Write remaining records
        if batch_records:
            with open(output_csv, mode, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerows(batch_records)
                f.flush()
                os.fsync(f.fileno())
        
        print(f"\n{'='*70}")
        print("Download Complete!")
        print(f"{'='*70}")
        print(f"Successfully downloaded: {success_count} stocks")
        print(f"Failed: {failure_count} stocks")
        print(f"Total price records: {total_records}")
        print(f"Output file: {output_csv}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download daily price data from Dhan API (parallel)')
    parser.add_argument('--client-id', type=str, required=True, help='Dhan API client ID')
    parser.add_argument('--access-token', type=str, required=True, help='Dhan API access token')
    parser.add_argument('--instruments', type=str, default='dhan_instruments.csv', help='Instruments CSV file')
    parser.add_argument('--start', type=int, default=0, help='Start index')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of stocks')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for checkpoints')
    parser.add_argument('--workers', type=int, default=10, help='Number of parallel workers (default: 10)')
    parser.add_argument('--output', type=str, default='monthly_price_data.csv', help='Output CSV file')
    
    args = parser.parse_args()
    
    downloader = DhanPriceDataDownloader(
        client_id=args.client_id,
        access_token=args.access_token
    )
    downloader.download_all_stocks(
        instruments_csv=args.instruments,
        output_csv=args.output,
        start_index=args.start,
        limit=args.limit,
        batch_size=args.batch_size,
        max_workers=args.workers
    )


if __name__ == "__main__":
    main()
