"""
MCPS12 Segment Analysis: Top 250 vs Rank 251-1000.
Also calculates and plots Investor Density (Total MC / Total Shareholders) per segment.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import warnings
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.mcps15_strategy import MCPS15Strategy
from utils.analytics import calculate_metrics

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

# --- Helper for Density Calculation ---
def get_quarter_for_date(date):
    y, m = date.year, date.month
    # Mapping to nearest previous quarter available in SH data
    # Assuming SH data comes with a lag, but here we want the "reporting" quarter
    # Standard quarters: Dec, Mar, Jun, Sep
    if m < 4: return f"Dec-{y-1}"
    elif m < 7: return f"Mar-{y}"
    elif m < 10: return f"Jun-{y}"
    else: return f"Sep-{y}"

def calculate_segment_density(dates, universe_size_cut=250):
    density_records = []
    
    for d in dates:
        # Get full universe
        univ = dh.get_universe(d, size=1000)
        if univ.empty: continue
        
        # Sort by MC
        univ = univ.sort_values('mc', ascending=False)
        
        # Split segments
        top250 = univ.iloc[:universe_size_cut]
        ex250 = univ.iloc[universe_size_cut:]
        
        q_label = get_quarter_for_date(d)
        sh_q = dh.shareholding_df[dh.shareholding_df['quarter'] == q_label]
        
        def get_density(df_segment):
            if df_segment.empty: return np.nan
            merged = pd.merge(df_segment, sh_q, on='isin')
            if merged.empty: return np.nan
            total_mc = merged['mc'].sum()
            total_sh = merged['total_shareholders'].sum()
            if total_sh == 0: return np.nan
            return total_mc / total_sh

        den_250 = get_density(top250)
        den_ex250 = get_density(ex250)
        
        density_records.append({
            'date': d,
            'density_top250': den_250,
            'density_ex250': den_ex250
        })
        
    return pd.DataFrame(density_records)

# --- Simulation Logic ---

def run_segment_sim(segment_name):
    print(f"Running MCPS12 for segment: {segment_name}...")
    start_date, end_date = "2018-01-01", "2026-02-05"
    all_dates = sorted(dh.get_all_dates())
    rdates = sorted([
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2018, 2027) for m in [2, 5, 8, 11]
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ])
    rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

    port = Portfolio(10000000)
    fee_model = FeeModel(0, 0)
    tax_man = TaxManager(0, 0)
    
    # Define strategy with custom universe filtering
    strat = MCPS15Strategy(dh, group_top_pct=0.50, num_stocks=12, universe_size=1000)
    
    # Helper to capture original universe method
    original_get_universe = dh.get_universe
    
    def patched_get_universe(d, size):
        # We always request Top 1000 then slice
        u = original_get_universe(d, 1000)
        if u.empty: return u
        u = u.sort_values('mc', ascending=False)
        
        if segment_name == 'Top250':
            return u.iloc[:250]
        else: # Ex250
            if len(u) <= 250: return pd.DataFrame()
            return u.iloc[250:]

    # Monkeypatch for this run
    dh.get_universe = patched_get_universe
    
    try:
        eng = SimEngine(dh, port, fee_model, tax_man, cash_yield_rate=0)
        eng.run(start_date, end_date, strat.calculate_selection, rdates, verbose=False)
    finally:
        # Restore
        dh.get_universe = original_get_universe
    
    return pd.DataFrame(port.nav_history)

# 1. Run Simulations
print("Starting Simulations...")
nav_top250 = run_segment_sim('Top250')
nav_ex250 = run_segment_sim('Ex250')

# 2. Calculate Density
print("Calculating Investor Density...")
# Use quarterly points for density to reduce noise
all_q_dates = pd.date_range(start="2018-01-01", end="2026-02-05", freq='Q')
# Map standard quarters to nearest trading days
trading_dates = sorted(dh.get_all_dates())
density_dates = []
for d in all_q_dates:
    valid = [td for td in trading_dates if td <= d]
    if valid: density_dates.append(valid[-1])

density_df = calculate_segment_density(density_dates)

# 3. Metrics
m_top250 = calculate_metrics(nav_top250)
m_ex250 = calculate_metrics(nav_ex250)

print("\n" + "="*50)
print(f"{'Metric':<15} | {'MCPS12 (Top 250)':<15} | {'MCPS12 (251-1000)':<15}")
print("-" * 50)
for k in m_top250.keys():
    print(f"{k:<15} | {m_top250[k]:<15} | {m_ex250[k]:<15}")
print("="*50)

# 4. Plotting (Dual Axis or Subplots)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
fig.patch.set_facecolor('#0d1117')

# Plot 1: Performance
ax1.set_facecolor('#0d1117')
ax1.plot(nav_top250['date'], nav_top250['nav'] / nav_top250['nav'].iloc[0] * 100, color='#00d4ff', linewidth=3, label='MCPS12 (Top 250)')
ax1.plot(nav_ex250['date'], nav_ex250['nav'] / nav_ex250['nav'].iloc[0] * 100, color='#ff9500', linewidth=3, label='MCPS12 (Rank 251-1000)')

ax1.set_title("MCPS12 Performance: Large vs Small Cap Segments", color='white', fontsize=16)
ax1.set_ylabel("Normalized NAV", color='white')
ax1.legend(facecolor='#1a1a2e', labelcolor='white', loc='upper left')
ax1.grid(True, color='#222222')
ax1.tick_params(colors='white')

# Plot 2: Investor Density
ax2.set_facecolor('#0d1117')
ax2.plot(density_df['date'], density_df['density_top250'], color='#00d4ff', linewidth=2, linestyle='--', label='Density Top 250')
ax2.plot(density_df['date'], density_df['density_ex250'], color='#ff9500', linewidth=2, linestyle='--', label='Density Ex-250')

ax2.set_title("Investor Density (Avg Market Cap per Shareholder)", color='white', fontsize=14)
ax2.set_ylabel("Density (MC/SH)", color='white')
ax2.legend(facecolor='#1a1a2e', labelcolor='white', loc='upper left')
ax2.grid(True, color='#222222')
ax2.tick_params(colors='white')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

plt.tight_layout()
out_path = repo_root / "mcps12_segments_with_density.png"
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved combined plot to: {out_path}")
# plt.show() # Disabled for headless env
