#!/usr/bin/env python
"""
Convert Benchmark Files from CSV to Parquet Format

Converts all industry and industry group benchmark timeseries files
from CSV to Parquet for faster loading.

Usage:
    python scripts/convert_benchmarks_to_parquet.py
"""

import pandas as pd
from pathlib import Path
import time

def convert_benchmarks_to_parquet():
    """Convert all benchmark timeseries CSV files to Parquet"""
    
    print("="*80)
    print("BENCHMARK CSV → PARQUET CONVERSION")
    print("="*80)
    
    benchmark_base = Path(__file__).parent.parent / 'analysis' / 'outputs' / 'benchmarks'
    
    converted_count = 0
    total_csv_size = 0
    total_parquet_size = 0
    
    # Convert industry benchmarks
    print("\n📊 Converting Industry Benchmarks...")
    industry_path = benchmark_base / 'industries'
    
    if industry_path.exists():
        for industry_folder in sorted(industry_path.glob('*/')):
            timeseries_csv = industry_folder / 'timeseries.csv'
            
            if timeseries_csv.exists():
                timeseries_parquet = industry_folder / 'timeseries.parquet'
                
                # Read CSV
                df = pd.read_csv(timeseries_csv)
                df['date'] = pd.to_datetime(df['date'])
                
                # Write Parquet
                df.to_parquet(timeseries_parquet, engine='pyarrow', 
                             compression='snappy', index=False)
                
                csv_size = timeseries_csv.stat().st_size / 1024  # KB
                parquet_size = timeseries_parquet.stat().st_size / 1024
                
                total_csv_size += csv_size
                total_parquet_size += parquet_size
                converted_count += 1
                
                if converted_count % 20 == 0:
                    print(f"  ✅ Converted {converted_count} industry benchmarks...")
        
        print(f"  ✅ Completed {converted_count} industry benchmarks")
    
    # Convert industry group benchmarks
    print("\n📊 Converting Industry Group Benchmarks...")
    group_path = benchmark_base / 'industry_groups'
    group_converted = 0
    
    if group_path.exists():
        for group_folder in sorted(group_path.glob('*/')):
            timeseries_csv = group_folder / 'timeseries.csv'
            
            if timeseries_csv.exists():
                timeseries_parquet = group_folder / 'timeseries.parquet'
                
                # Read CSV
                df = pd.read_csv(timeseries_csv)
                df['date'] = pd.to_datetime(df['date'])
                
                # Write Parquet
                df.to_parquet(timeseries_parquet, engine='pyarrow',
                             compression='snappy', index=False)
                
                csv_size = timeseries_csv.stat().st_size / 1024  # KB
                parquet_size = timeseries_parquet.stat().st_size / 1024
                
                total_csv_size += csv_size
                total_parquet_size += parquet_size
                group_converted += 1
        
        print(f"  ✅ Completed {group_converted} industry group benchmarks")
    
    converted_count += group_converted
    
    # Convert index benchmarks (if any CSV files)
    print("\n📊 Converting Index Benchmarks...")
    index_converted = 0
    
    for csv_file in benchmark_base.glob('*.csv'):
        if 'summary' not in csv_file.name.lower():  # Skip summary files
            parquet_file = csv_file.with_suffix('.parquet')
            
            df = pd.read_csv(csv_file)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            df.to_parquet(parquet_file, engine='pyarrow',
                         compression='snappy', index=False)
            
            csv_size = csv_file.stat().st_size / 1024
            parquet_size = parquet_file.stat().st_size / 1024
            
            total_csv_size += csv_size
            total_parquet_size += parquet_size
            index_converted += 1
    
    if index_converted > 0:
        print(f"  ✅ Completed {index_converted} index benchmarks")
    
    converted_count += index_converted
    
    # Summary
    print(f"\n{'='*80}")
    print("✅ BENCHMARK CONVERSION COMPLETE")
    print(f"{'='*80}")
    print(f"\n📊 Summary:")
    print(f"   Total files converted: {converted_count}")
    print(f"   CSV total size:        {total_csv_size:8.1f} KB ({total_csv_size/1024:.2f} MB)")
    print(f"   Parquet total size:    {total_parquet_size:8.1f} KB ({total_parquet_size/1024:.2f} MB)")
    print(f"   Space saved:           {total_csv_size - total_parquet_size:8.1f} KB ({(1 - total_parquet_size/total_csv_size)*100:.1f}% reduction)")
    
    print(f"\n🚀 Usage in your code:")
    print(f"   # Before:")
    print(f"   df = pd.read_csv('analysis/outputs/benchmarks/industries/Pharmaceuticals/timeseries.csv')")
    print(f"")
    print(f"   # After (3-5x faster):")
    print(f"   df = pd.read_parquet('analysis/outputs/benchmarks/industries/Pharmaceuticals/timeseries.parquet')")


def main():
    """Main execution"""
    try:
        convert_benchmarks_to_parquet()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
