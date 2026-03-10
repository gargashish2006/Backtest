#!/usr/bin/env python
"""
Update Python Scripts to Use Parquet Instead of CSV

This utility helps update your analysis scripts to use Parquet format
instead of CSV for faster data loading.

Usage:
    python scripts/update_scripts_to_parquet.py
    
The script will:
1. Find all Python files that read database/benchmark CSV files
2. Show you the changes it will make
3. Ask for confirmation before updating
4. Create backups of modified files
"""

import re
from pathlib import Path
from datetime import datetime
import sys

def find_python_files(base_path):
    """Find all Python files in the project"""
    paths_to_search = [
        base_path / 'scripts',
        base_path / 'analysis' / 'scripts',
        base_path,  # Root level scripts
    ]
    
    python_files = []
    for path in paths_to_search:
        if path.exists():
            python_files.extend(path.glob('*.py'))
    
    # Exclude this script and conversion scripts
    excluded = {'update_scripts_to_parquet.py', 'convert_to_parquet.py', 
                'convert_benchmarks_to_parquet.py', 'test_parquet_performance.py'}
    python_files = [f for f in python_files if f.name not in excluded]
    
    return python_files

def find_csv_reads(content):
    """Find all pd.read_csv calls for database and benchmark files"""
    patterns = [
        # Database files
        (r"pd\.read_csv\(['\"]database/([a-zA-Z_]+)\.csv['\"]([^)]*)\)",
         r"pd.read_parquet('database/\1.parquet'\2)"),
        
        # Benchmark files (industries)
        (r"pd\.read_csv\(['\"]analysis/outputs/benchmarks/industries/([^/]+)/timeseries\.csv['\"]([^)]*)\)",
         r"pd.read_parquet('analysis/outputs/benchmarks/industries/\1/timeseries.parquet'\2)"),
        
        # Benchmark files (industry_groups)
        (r"pd\.read_csv\(['\"]analysis/outputs/benchmarks/industry_groups/([^/]+)/timeseries\.csv['\"]([^)]*)\)",
         r"pd.read_parquet('analysis/outputs/benchmarks/industry_groups/\1/timeseries.parquet'\2)"),
        
        # Benchmark files (index)
        (r"pd\.read_csv\(['\"]analysis/outputs/benchmarks/index/([^/]+)/timeseries\.csv['\"]([^)]*)\)",
         r"pd.read_parquet('analysis/outputs/benchmarks/index/\1/timeseries.parquet'\2)"),
    ]
    
    changes = []
    for pattern, replacement in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            old_text = match.group(0)
            new_text = re.sub(pattern, replacement, old_text)
            changes.append((match.start(), match.end(), old_text, new_text))
    
    return changes

def preview_changes(file_path, changes):
    """Show a preview of changes for a file"""
    print(f"\n{'='*80}")
    print(f"📄 {file_path.name}")
    print(f"{'='*80}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    for start, end, old_text, new_text in changes:
        # Find line number
        line_num = content[:start].count('\n') + 1
        
        print(f"\n  Line {line_num}:")
        print(f"  ❌ OLD: {old_text}")
        print(f"  ✅ NEW: {new_text}")

def apply_changes(file_path, changes, create_backup=True):
    """Apply changes to a file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create backup
    if create_backup:
        backup_path = file_path.with_suffix(f'.csv_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.py')
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"  💾 Backup created: {backup_path.name}")
    
    # Apply changes in reverse order to maintain positions
    for start, end, old_text, new_text in sorted(changes, reverse=True):
        content = content[:start] + new_text + content[end:]
    
    # Write updated content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"  ✅ Updated: {file_path.name}")

def main():
    """Main execution"""
    base_path = Path(__file__).parent.parent
    
    print("="*80)
    print("UPDATE SCRIPTS TO USE PARQUET FORMAT")
    print("="*80)
    
    # Find Python files
    print("\n🔍 Scanning for Python files...")
    python_files = find_python_files(base_path)
    print(f"   Found {len(python_files)} Python files")
    
    # Find files with CSV reads
    files_to_update = {}
    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            changes = find_csv_reads(content)
            if changes:
                files_to_update[file_path] = changes
        except Exception as e:
            print(f"   ⚠️  Error reading {file_path.name}: {e}")
    
    if not files_to_update:
        print("\n✅ No CSV reads found - all scripts already updated!")
        return 0
    
    # Show preview
    print(f"\n📊 Found {len(files_to_update)} files to update:")
    total_changes = sum(len(changes) for changes in files_to_update.values())
    print(f"   Total changes: {total_changes}")
    
    for file_path, changes in files_to_update.items():
        preview_changes(file_path, changes)
    
    # Ask for confirmation
    print(f"\n{'='*80}")
    response = input("\n❓ Apply these changes? [y/N]: ").strip().lower()
    
    if response != 'y':
        print("\n❌ Cancelled - no changes made")
        return 0
    
    # Apply changes
    print(f"\n{'='*80}")
    print("🔄 APPLYING CHANGES")
    print(f"{'='*80}")
    
    for file_path, changes in files_to_update.items():
        try:
            apply_changes(file_path, changes, create_backup=True)
        except Exception as e:
            print(f"   ❌ Error updating {file_path.name}: {e}")
    
    print(f"\n{'='*80}")
    print("✅ UPDATE COMPLETE")
    print(f"{'='*80}")
    print(f"\n📊 Summary:")
    print(f"   Files updated:   {len(files_to_update)}")
    print(f"   Total changes:   {total_changes}")
    print(f"   Backups created: {len(files_to_update)}")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Test your updated scripts to ensure they work correctly")
    print(f"   2. If everything works, you can delete the .csv_backup_* files")
    print(f"   3. Enjoy 8-66x faster data loading! ⚡")
    
    return 0

if __name__ == "__main__":
    exit(main())
