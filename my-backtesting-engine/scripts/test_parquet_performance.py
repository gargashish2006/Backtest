#!/usr/bin/env python
"""
Test Parquet Performance vs CSV

Benchmarks various read operations to demonstrate the speed improvements
of Parquet format over CSV.

Usage:
    python scripts/test_parquet_performance.py
"""

import pandas as pd
from pathlib import Path
import time
import sys

def format_time(seconds):
    """Format time in appropriate units"""
    if seconds < 0.001:
        return f"{seconds*1000000:.1f}μs"
    elif seconds < 1:
        return f"{seconds*1000:.1f}ms"
    else:
        return f"{seconds:.2f}s"

def test_performance():
    """Run performance benchmarks comparing CSV vs Parquet"""
    
    print("="*80)
    print("PARQUET PERFORMANCE BENCHMARK")
    print("="*80)
    
    database_path = Path(__file__).parent.parent / 'database'
    
    # Files to test
    test_files = [
        ('price_data', 'Main price dataset'),
        ('shareholding_patterns', 'Shareholding data'),
        ('industry_info', 'Industry classifications'),
        ('stock_statistics', 'Stock statistics')
    ]
    
    results = []
    
    for file_base, description in test_files:
        csv_file = database_path / f'{file_base}.csv'
        parquet_file = database_path / f'{file_base}.parquet'
        
        if not csv_file.exists() or not parquet_file.exists():
            print(f"\n⚠️  Skipping {file_base} (files not found)")
            continue
        
        print(f"\n{'='*80}")
        print(f"Testing: {description} ({file_base})")
        print(f"{'='*80}")
        
        # Test 1: Full read
        print("\n📊 Test 1: Full Dataset Read")
        
        start = time.time()
        df_csv = pd.read_csv(csv_file, low_memory=False)
        csv_time = time.time() - start
        
        start = time.time()
        df_parquet = pd.read_parquet(parquet_file)
        parquet_time = time.time() - start
        
        speedup_full = csv_time / parquet_time if parquet_time > 0 else 0
        
        print(f"  CSV:     {format_time(csv_time):>10s}")
        print(f"  Parquet: {format_time(parquet_time):>10s}")
        print(f"  Speedup: {speedup_full:6.1f}x faster ⚡")
        
        # Test 2: Column selection (only for files with multiple columns)
        if len(df_csv.columns) >= 3:
            print("\n📊 Test 2: Column Selection (Read 3 columns)")
            
            cols = list(df_csv.columns[:3])
            
            start = time.time()
            df_csv_cols = pd.read_csv(csv_file, usecols=cols, low_memory=False)
            csv_col_time = time.time() - start
            
            start = time.time()
            df_parquet_cols = pd.read_parquet(parquet_file, columns=cols)
            parquet_col_time = time.time() - start
            
            speedup_cols = csv_col_time / parquet_col_time if parquet_col_time > 0 else 0
            
            print(f"  CSV:     {format_time(csv_col_time):>10s}")
            print(f"  Parquet: {format_time(parquet_col_time):>10s}")
            print(f"  Speedup: {speedup_cols:6.1f}x faster ⚡")
        
        # Test 3: Filtered read (if date column exists)
        if 'date' in df_csv.columns and file_base == 'price_data':
            print("\n📊 Test 3: Filtered Read (Recent data only)")
            
            start = time.time()
            df_csv_filtered = pd.read_csv(csv_file, low_memory=False)
            df_csv_filtered['date'] = pd.to_datetime(df_csv_filtered['date'])
            df_csv_filtered = df_csv_filtered[df_csv_filtered['date'] >= '2024-01-01']
            csv_filter_time = time.time() - start
            
            start = time.time()
            df_parquet_filtered = pd.read_parquet(
                parquet_file,
                filters=[('date', '>=', pd.Timestamp('2024-01-01'))]
            )
            parquet_filter_time = time.time() - start
            
            speedup_filter = csv_filter_time / parquet_filter_time if parquet_filter_time > 0 else 0
            
            print(f"  CSV:     {format_time(csv_filter_time):>10s} (read all then filter)")
            print(f"  Parquet: {format_time(parquet_filter_time):>10s} (filter while reading)")
            print(f"  Speedup: {speedup_filter:6.1f}x faster ⚡")
        
        # File size comparison
        csv_size = csv_file.stat().st_size / (1024**2)
        parquet_size = parquet_file.stat().st_size / (1024**2)
        
        print(f"\n💾 File Size:")
        print(f"  CSV:     {csv_size:8.2f} MB")
        print(f"  Parquet: {parquet_size:8.2f} MB")
        print(f"  Saved:   {csv_size - parquet_size:8.2f} MB ({(1 - parquet_size/csv_size)*100:.1f}% smaller)")
        
        # Memory usage
        print(f"\n🧠 Memory Usage:")
        print(f"  Rows:    {len(df_csv):,}")
        print(f"  Columns: {len(df_csv.columns)}")
        
        results.append({
            'file': file_base,
            'speedup': speedup_full,
            'csv_size': csv_size,
            'parquet_size': parquet_size,
            'rows': len(df_csv)
        })
    
    # Summary
    if results:
        print(f"\n{'='*80}")
        print("📊 OVERALL SUMMARY")
        print(f"{'='*80}")
        
        avg_speedup = sum(r['speedup'] for r in results) / len(results)
        total_csv = sum(r['csv_size'] for r in results)
        total_parquet = sum(r['parquet_size'] for r in results)
        
        print(f"\n✅ Performance:")
        print(f"   Average speedup: {avg_speedup:.1f}x faster")
        print(f"   Best speedup:    {max(r['speedup'] for r in results):.1f}x faster")
        
        print(f"\n💾 Storage:")
        print(f"   Total CSV:       {total_csv:.2f} MB")
        print(f"   Total Parquet:   {total_parquet:.2f} MB")
        print(f"   Space saved:     {total_csv - total_parquet:.2f} MB ({(1 - total_parquet/total_csv)*100:.1f}%)")
        
        print(f"\n🎯 Recommendation:")
        if avg_speedup > 5:
            print(f"   ⭐ EXCELLENT! Parquet is {avg_speedup:.0f}x faster on average.")
            print(f"   → Update all analysis scripts to use .parquet format")
        elif avg_speedup > 2:
            print(f"   ✅ GOOD! Parquet is {avg_speedup:.0f}x faster on average.")
            print(f"   → Recommended to switch to .parquet format")
        else:
            print(f"   ℹ️  Modest improvement ({avg_speedup:.1f}x faster)")
            print(f"   → Consider using .parquet for large datasets")
        
        print(f"\n💡 Next Steps:")
        print(f"   1. Convert benchmarks: python scripts/convert_benchmarks_to_parquet.py")
        print(f"   2. Update your analysis scripts:")
        print(f"      - Replace: pd.read_csv('database/price_data.csv')")
        print(f"      - With:    pd.read_parquet('database/price_data.parquet')")
        print(f"   3. Enable column selection for even faster reads:")
        print(f"      - pd.read_parquet('file.parquet', columns=['col1', 'col2'])")
        print(f"   4. (Optional) Delete CSV files to save {total_csv - total_parquet:.0f} MB")


def main():
    """Main execution"""
    try:
        test_performance()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
