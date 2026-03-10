#!/usr/bin/env python
"""
Convert Database from CSV to Parquet Format

Benefits:
- 88% smaller files (613 MB → 70 MB)
- 10-20x faster loading
- 50-100x faster filtered queries
- Column-level compression and selection
- Industry standard format

Usage:
    python scripts/convert_to_parquet.py
"""

import pandas as pd
from pathlib import Path
import time

def convert_database_to_parquet():
    """Convert all database CSV files to Parquet format"""
    
    print("="*80)
    print("DATABASE CSV → PARQUET CONVERSION")
    print("="*80)
    
    database_path = Path(__file__).parent.parent / 'database'
    
    conversions = {
        'master_identifiers.csv': {
            'output': 'master_identifiers.parquet',
            'dtypes': {'isin': 'str', 'company_name': 'str', 'nse_symbol': 'str', 'bse_symbol': 'str'}
        },
        'price_data.csv': {
            'output': 'price_data.parquet',
            'dtypes': {'isin': 'str', 'company_name': 'str', 'symbol': 'str', 
                      'exchange': 'str', 'close': 'float32', 'open': 'float32',
                      'high': 'float32', 'low': 'float32', 'volume': 'float32'},
            'date_cols': ['date']
        },
        'shareholding_patterns.csv': {
            'output': 'shareholding_patterns.parquet',
            'dtypes': {'isin': 'str', 'company_name': 'str', 'quarter': 'str', 'data_source': 'str'}
        },
        'industry_info.csv': {
            'output': 'industry_info.parquet',
            'dtypes': {'isin': 'str', 'company_name': 'str', 'nse_symbol': 'str', 
                      'industry': 'str', 'industry_group': 'str'}
        },
        'stock_statistics.csv': {
            'output': 'stock_statistics.parquet',
            'dtypes': {'isin': 'str', 'company_name': 'str', 'nse_symbol': 'str'},
            'date_cols': ['price_start_date', 'price_end_date', 'shp_start_date', 'shp_end_date']
        }
    }
    
    total_csv_size = 0
    total_parquet_size = 0
    
    for csv_file, config in conversions.items():
        csv_path = database_path / csv_file
        
        if not csv_path.exists():
            print(f"\n⚠️  {csv_file} not found, skipping...")
            continue
        
        print(f"\n{'='*80}")
        print(f"Converting: {csv_file}")
        print(f"{'='*80}")
        
        parquet_path = database_path / config['output']
        
        # Read CSV
        start_time = time.time()
        print("  Reading CSV...", end="", flush=True)
        
        df = pd.read_csv(csv_path, dtype=config.get('dtypes', {}), low_memory=False)
        
        # Convert date columns
        for date_col in config.get('date_cols', []):
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        
        read_time = time.time() - start_time
        print(f" Done ({read_time:.2f}s)")
        
        # Write Parquet with compression
        print("  Writing Parquet...", end="", flush=True)
        start_time = time.time()
        
        df.to_parquet(
            parquet_path,
            engine='pyarrow',
            compression='snappy',  # Fast compression (alternatives: 'gzip', 'zstd')
            index=False
        )
        
        write_time = time.time() - start_time
        print(f" Done ({write_time:.2f}s)")
        
        # Compare sizes
        csv_size = csv_path.stat().st_size / (1024**2)  # MB
        parquet_size = parquet_path.stat().st_size / (1024**2)
        
        total_csv_size += csv_size
        total_parquet_size += parquet_size
        
        print(f"\n  📊 Results:")
        print(f"     CSV size:     {csv_size:8.2f} MB")
        print(f"     Parquet size: {parquet_size:8.2f} MB")
        print(f"     Reduction:    {(1 - parquet_size/csv_size)*100:7.1f}%")
        print(f"     Rows:         {len(df):,}")
        print(f"     Columns:      {len(df.columns)}")
        
        # Quick read benchmark
        print(f"\n  ⚡ Speed Test:")
        start = time.time()
        _ = pd.read_csv(csv_path, nrows=10000)
        csv_time = time.time() - start
        
        start = time.time()
        _ = pd.read_parquet(parquet_path)
        parquet_time = time.time() - start
        
        speedup = csv_time / parquet_time if parquet_time > 0 else 0
        print(f"     CSV read:     {csv_time:.3f}s")
        print(f"     Parquet read: {parquet_time:.3f}s")
        print(f"     Speedup:      {speedup:.1f}x faster")

    print(f"\n{'='*80}")
    print("✅ CONVERSION COMPLETE")
    print(f"{'='*80}")
    print(f"\n📊 Total Storage:")
    print(f"   CSV total:     {total_csv_size:8.2f} MB")
    print(f"   Parquet total: {total_parquet_size:8.2f} MB")
    print(f"   Saved:         {total_csv_size - total_parquet_size:8.2f} MB ({(1 - total_parquet_size/total_csv_size)*100:.1f}% reduction)")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Test parquet files with: python scripts/test_parquet_performance.py")
    print(f"   2. Update analysis scripts to use .parquet instead of .csv")
    print(f"   3. Convert benchmarks: python scripts/convert_benchmarks_to_parquet.py")
    print(f"   4. (Optional) Keep CSVs as backup or delete to save space")
    
    print(f"\n💡 Usage Example:")
    print(f"   # Before:")
    print(f"   df = pd.read_csv('database/price_data.csv')")
    print(f"")
    print(f"   # After (10-20x faster):")
    print(f"   df = pd.read_parquet('database/price_data.parquet')")
    print(f"")
    print(f"   # Even faster (column selection):")
    print(f"   df = pd.read_parquet('database/price_data.parquet',")
    print(f"                        columns=['isin', 'date', 'close'])")
    print(f"")
    print(f"   # Super fast (filtered reading):")
    print(f"   df = pd.read_parquet('database/price_data.parquet',")
    print(f"                        filters=[('date', '>=', '2024-01-01')])")


def main():
    """Main execution"""
    try:
        convert_database_to_parquet()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
