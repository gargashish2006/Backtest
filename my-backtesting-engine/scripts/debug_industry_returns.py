
import pandas as pd
import numpy as np
from pathlib import Path

# Setup paths
base_path = Path(__file__).parent.parent
ind_path = base_path / 'analysis/outputs/benchmarks/industries'

# Picks a sample industry
industry = 'Breweries_&_Distilleries'
daily_file = ind_path / industry / 'timeseries.csv'

# Load Daily Data
df = pd.read_csv(daily_file)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')

# Calculate Quarterly Returns from Daily Data (Compounded)
# We want to see what the return is for a quarter using daily data
# vs just taking End Price / Start Price - 1

print(f"DEBUGGING INDUSTRY: {industry}")
print("-" * 60)

# Resample to quarterly to see the compounded effect
# Quarter ends
dates = pd.date_range('2017-03-31', '2025-12-31', freq='QE')

print(f"{'Quarter End':<15} | {'Daily Compounded':<20} | {' constituents':<15}")
print("-" * 60)

for i in range(len(dates)-1):
    start = dates[i]
    end = dates[i+1]
    
    mask = (df['date'] > start) & (df['date'] <= end)
    period_df = df[mask]
    
    if period_df.empty:
        continue
        
    # Compounding daily returns
    # Daily returns are in percent, so /100 + 1
    daily_rets = period_df['return'] / 100
    compounded = (1 + daily_rets).prod() - 1
    
    avg_const = period_df['num_constituents'].mean()
    
    print(f"{end.date()} | {compounded*100:18.2f}% | {avg_const:13.1f}")

print("-" * 60)
