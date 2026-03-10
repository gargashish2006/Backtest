#!/usr/bin/env python3
"""
Pre-flight check before updating price data.
Verifies all prerequisites are met.
"""

import os
import sys
from pathlib import Path
import pandas as pd

def check_credentials():
    """Check if Dhan API credentials are set."""
    client_id = os.getenv('DHAN_CLIENT_ID')
    access_token = os.getenv('DHAN_ACCESS_TOKEN')
    
    if not client_id or not access_token:
        print("❌ Dhan API credentials not set!")
        print("\nPlease set the following environment variables:")
        print("  export DHAN_CLIENT_ID=\"your_client_id\"")
        print("  export DHAN_ACCESS_TOKEN=\"your_access_token\"")
        return False
    
    print(f"✅ DHAN_CLIENT_ID: {client_id[:10]}***")
    print(f"✅ DHAN_ACCESS_TOKEN: {access_token[:10]}***")
    return True

def check_files():
    """Check if required files exist."""
    project_root = Path(__file__).parent
    
    required_files = {
        'Instruments': project_root / 'archive/source_data/dhan_instruments.csv',
        'Price DB': project_root / 'database/price_data.parquet',
        'Master IDs': project_root / 'database/master_identifiers.parquet',
        'Update Script': project_root / 'scripts/update_price_data.py',
    }
    
    all_exist = True
    for name, path in required_files.items():
        if path.exists():
            if name == 'Instruments':
                import csv
                with open(path, 'r') as f:
                    count = sum(1 for _ in csv.DictReader(f))
                print(f"✅ {name}: {path.name} ({count:,} instruments)")
            elif name == 'Price DB':
                df = pd.read_parquet(path)
                print(f"✅ {name}: {path.name} ({len(df):,} records)")
            else:
                print(f"✅ {name}: {path.name}")
        else:
            print(f"❌ {name}: NOT FOUND at {path}")
            all_exist = False
    
    return all_exist

def check_current_status():
    """Check current database status."""
    project_root = Path(__file__).parent
    db_path = project_root / 'database/price_data.parquet'
    
    df = pd.read_parquet(db_path)
    df['date'] = pd.to_datetime(df['date'])
    
    print(f"\n📊 Current Database Status:")
    print(f"   Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"   Total records: {len(df):,}")
    print(f"   Unique stocks: {df['isin'].nunique():,}")
    
    # Check most recent dates
    recent = df.groupby('date').size().tail(5)
    print(f"\n   Recent trading days:")
    for date, count in recent.items():
        print(f"     {date.date()}: {count:,} stocks")
    
    last_date = df['date'].max().date()
    from datetime import date
    today = date.today()
    days_behind = (today - last_date).days
    
    if days_behind > 0:
        print(f"\n⚠️  Data is {days_behind} days behind (last: {last_date}, today: {today})")
        print(f"   You need to update from {last_date + pd.Timedelta(days=1)} to {today}")
    else:
        print(f"\n✅ Data is up to date!")
    
    return last_date, today

def main():
    print("=" * 60)
    print("Pre-flight Check: Price Data Update")
    print("=" * 60)
    print()
    
    # Check 1: Credentials
    print("1️⃣  Checking Dhan API Credentials...")
    creds_ok = check_credentials()
    print()
    
    # Check 2: Files
    print("2️⃣  Checking Required Files...")
    files_ok = check_files()
    print()
    
    # Check 3: Current Status
    print("3️⃣  Checking Current Data Status...")
    last_date, today = check_current_status()
    print()
    
    # Summary
    print("=" * 60)
    if creds_ok and files_ok:
        print("✅ All checks passed! Ready to update.")
        print()
        print("To update, run:")
        print(f"  python3 scripts/update_price_data.py {last_date + pd.Timedelta(days=1)} {today} --workers 10")
        print()
        print("Or use the convenience script:")
        print("  ./update_to_latest.sh")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
