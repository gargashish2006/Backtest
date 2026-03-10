#!/usr/bin/env python
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

# Import Strategies
from strategies.industry_group.Sync15_Top1000_Large_Champion_10022026 import Sync15_Top1000_Large_Champion_10022026
from strategies.industry_group.Sync15_Top1000_Small_Champion_10022026 import Sync15_Top1000_Small_Champion_10022026
from strategies.industry_group.Sync15_RSNP_Top1000_Large import Sync15_RSNP_Top1000_Large
from strategies.industry_group.Sync15_RSNP_Top1000_Small import Sync15_RSNP_Top1000_Small

# Universal Friction Analysis Helper
def calculate_metrics(df, strategies_name):
    if df.empty:
        return {'Strategy': strategies_name, 'CAGR': 0, 'MaxDD': 0, 'Sharpe': 0}
    
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # CAGR
    start_val = df['value'].iloc[0]
    end_val = df['value'].iloc[-1]
    days = (df.index[-1] - df.index[0]).days
    cagr = (end_val / start_val) ** (365.25 / days) - 1
    
    # Max Drawdown
    roll_max = df['value'].cummax()
    drawdown = (df['value'] - roll_max) / roll_max
    max_dd = drawdown.min()
    
    # Sharpe (Quarterly data approximation)
    # Using simple returns of the equity curve
    # Logic: Convert to daily/monthly if possible, but here we have quarterly execution snapshots
    # If df has daily values (it should from equity_curve), good.
    # The strategies return 'equity_curve' which usually has snapshot dates.
    # We'll stick to a simple approx if it's quarterly.
    # But wait, the strategies print 'Value' at each rebalance. The returned DF is that series.
    # It's quarterly.
    pct_change = df['value'].pct_change().dropna()
    # Quarterly Sharpe = Mean / Std * sqrt(4)
    if pct_change.std() == 0:
        sharpe = 0
    else:
        sharpe = (pct_change.mean() / pct_change.std()) * (4**0.5)
        
    return {
        'Strategy': strategies_name,
        'Net CAGR': cagr * 100,
        'Max Drawdown': max_dd * 100,
        'Sharpe Ratio': sharpe,
        'Final Value': end_val
    }

results = []

print("="*100)
print("RUNNING RSNP SENSITIVITY ANALYSIS (NET NET 1% FRICTION)")
print("="*100)

# 1. BASE STRATEGIES + RSNP FILTER (0.34)
# ---------------------------------------
print("\n--- EXPERIMENT A: Base Strategies + RSNP >= 0.34 ---")

# Large Cap
print("\n1. Base Large (1000) + RSNP 34")
strat = Sync15_Top1000_Large_Champion_10022026()
strat.RSNP_THRESHOLD_FILTER = 0.34 # Activate Filter
df = strat.run()
results.append(calculate_metrics(df, "Base Large (1000) + RSNP 0.34"))

# Small Cap
print("\n2. Base Small (1000) + RSNP 34")
strat = Sync15_Top1000_Small_Champion_10022026()
strat.RSNP_THRESHOLD_FILTER = 0.34 # Activate Filter
df = strat.run()
results.append(calculate_metrics(df, "Base Small (1000) + RSNP 0.34"))


# 2. MOMENTUM STRATEGIES - NO RSNP FILTER (0.00)
# ----------------------------------------------
print("\n--- EXPERIMENT B: Momentum Strategies - RSNP REMOVED (0.00) ---")

# Large Cap
print("\n3. Momentum Large (1000) NO THRESHOLD")
strat = Sync15_RSNP_Top1000_Large()
strat.RSNP_THRESHOLD = 0.0 # Disable Filter (Default is 0.34)
df = strat.run()
results.append(calculate_metrics(df, "Momentum Large (1000) NO RSNP"))

# Small Cap
print("\n4. Momentum Small (1000) NO THRESHOLD")
strat = Sync15_RSNP_Top1000_Small()
strat.RSNP_THRESHOLD = 0.0 # Disable Filter
df = strat.run()
results.append(calculate_metrics(df, "Momentum Small (1000) NO RSNP"))

# 3. BASELINES (FOR COMPARISON) - OPTIONAL IF WE HAVE THEM, BUT RUNNING FOR BECHMARK
# We can just verify against known numbers or run them here to be sure of apples-to-apples in this run
print("\n--- BASELINES (CONTROL) ---")

print("\n5. Base Large (1000) [Control]")
strat = Sync15_Top1000_Large_Champion_10022026()
strat.RSNP_THRESHOLD_FILTER = 0.0
df = strat.run()
results.append(calculate_metrics(df, "Base Large (1000) [Control]"))

print("\n6. Momentum Large (1000) [Control]")
strat = Sync15_RSNP_Top1000_Large()
# Default RSNP_THRESHOLD is 0.34
df = strat.run()
results.append(calculate_metrics(df, "Momentum Large (1000) [Control]"))


# COMPILE RESULTS
final_df = pd.DataFrame(results)
final_df = final_df.sort_values('Net CAGR', ascending=False)

print("\n" + "="*100)
print("FINAL RESULTS TABLE")
print("="*100)
print(final_df.to_string(index=False))

# Save
out_path = Path(__file__).parent / 'outputs' / 'rsnp_sensitivity_results.csv'
final_df.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")
