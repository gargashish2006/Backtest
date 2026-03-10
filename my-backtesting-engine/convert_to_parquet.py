"""
Convert price_data.csv to Parquet format using Dask for parallel processing
This will significantly speed up data loading in backtests
"""
import dask.dataframe as dd
import pandas as pd
from pathlib import Path
import time

print('='*80)
print('CONVERTING CSV TO PARQUET (Using Dask - Parallel Processing)')
print('='*80)
print()

start_time = time.time()

# Read CSV with Dask (parallel, chunked, doesn't load all into memory)
print('Step 1: Reading price_data.csv with Dask...')
print('  (This processes in parallel chunks - much faster!)')
print()

df = dd.read_csv(
    'database/price_data.csv',
    dtype={
        'isin': 'category',
        'symbol': 'category',
        'company_name': 'category',
        'exchange': 'category',
        'open': 'float32',
        'high': 'float32',
        'low': 'float32',
        'close': 'float32',
        'volume': 'int32'
    },
    parse_dates=['date'],
    blocksize='50MB'  # Process 50MB chunks
)

print(f'  Data structure created (lazy evaluation)')
print(f'  Partitions: {df.npartitions}')
print()

# Convert to Parquet (this triggers computation)
print('Step 2: Converting to Parquet format...')
print('  (Writing optimized binary format with compression)')
print()

df.to_parquet(
    'database/price_data.parquet',
    engine='pyarrow',
    compression='snappy',
    write_index=False
)

elapsed = time.time() - start_time
print()
print('='*80)
print('✅ CONVERSION COMPLETE!')
print('='*80)
print()

# Check file sizes
csv_size = Path('database/price_data.csv').stat().st_size / (1024**2)
parquet_path = Path('database/price_data.parquet')

if parquet_path.is_dir():
    # Dask creates a directory with multiple parquet files
    parquet_size = sum(f.stat().st_size for f in parquet_path.rglob('*.parquet')) / (1024**2)
else:
    parquet_size = parquet_path.stat().st_size / (1024**2)

print(f'Original CSV:  {csv_size:.1f} MB')
print(f'Parquet:       {parquet_size:.1f} MB')
print(f'Space saved:   {csv_size - parquet_size:.1f} MB ({(1 - parquet_size/csv_size)*100:.1f}%)')
print()
print(f'Conversion time: {elapsed:.1f} seconds')
print()
print('='*80)
print('NEXT STEPS:')
print('='*80)
print('1. Update momentum_strategy.py to read from .parquet')
print('2. Expected speedup: 10-20x faster data loading')
print('3. Run Top 500/25 and Top 1000/50 strategies')
print('='*80)
