import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import sys
REPO_ROOT = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
sys.path.append(str(REPO_ROOT))

from data.data_handler import DataHandler

def get_quarter_labels(date: pd.Timestamp, lookback_quarters: int = 1):
    """Simple quarter mapping logic for aggregation."""
    quarters = ["Mar", "Jun", "Sep", "Dec"]
    year = date.year
    month = date.month
    
    # Determine 'Current' Quarter
    if month >= 2 and month < 5:
        curr_code, base_year = "Dec", year - 1
    elif month >= 5 and month < 8:
        curr_code, base_year = "Mar", year
    elif month >= 8 and month < 11:
        curr_code, base_year = "Jun", year
    else:
        curr_code, base_year = "Sep", year if month >= 11 else year - 1
        
    curr_q = f"{curr_code}-{base_year}"
    
    # Linear index for easier subtraction
    start_map = {"Mar": 0, "Jun": 1, "Sep": 2, "Dec": 3}
    linear_curr = (base_year * 4) + start_map[curr_code]
    linear_prev = linear_curr - lookback_quarters
    
    prev_year = linear_prev // 4
    prev_code = quarters[linear_prev % 4]
    prev_q = f"{prev_code}-{prev_year}"
    
    return curr_q, prev_q

def analyze_ownership():
    print("Loading Data...")
    dh = DataHandler(REPO_ROOT / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    sh_df = dh.shareholding_df
    if sh_df is None:
        print("Shareholding data not loaded.")
        return

    all_dates = sorted(dh.get_all_dates())
    # Define rebalance dates (approx middle of each quarter)
    raw_dates = [
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2018, 2027) for m in [2, 5, 8, 11]
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ]
    quarterly_dates = sorted(list(set(raw_dates))) # Fix duplicates
    
    results = []
    
    for dt in quarterly_dates:
        curr_q, prev_q = get_quarter_labels(dt, 1)
        print(f"Processing {dt.strftime('%Y-%m-%d')} (Current: {curr_q}, Prev: {prev_q})...")
        
        # Get Top 1000 stocks at this point
        universe = dh.get_universe(dt, size=1000)
        if universe.empty: continue
        isins = universe['isin'].tolist()
        
        # Get shareholding changes
        curr_sh = sh_df[sh_df['quarter'] == curr_q].copy()
        prev_sh = sh_df[sh_df['quarter'] == prev_q].copy()
        
        if curr_sh.empty or prev_sh.empty: continue
        
        # Merge for changes
        merged = pd.merge(
            curr_sh[['isin', 'promoter_holding_pct', 'fii_holding_pct', 'dii_holding_pct']],
            prev_sh[['isin', 'promoter_holding_pct', 'fii_holding_pct', 'dii_holding_pct']],
            on='isin', suffixes=('_curr', '_prev')
        )
        
        # Filter for Top 1000
        merged = merged[merged['isin'].isin(isins)]
        
        if merged.empty: continue
        
        # Calculate Deltas
        merged['p_chg'] = merged['promoter_holding_pct_curr'] - merged['promoter_holding_pct_prev']
        merged['f_chg'] = merged['fii_holding_pct_curr'] - merged['fii_holding_pct_prev']
        merged['d_chg'] = merged['dii_holding_pct_curr'] - merged['dii_holding_pct_prev']
        
        # Record Stats
        res = {
            'date': dt,
            'quarter': curr_q,
            'p_mean': merged['p_chg'].mean(),
            'p_median': merged['p_chg'].median(),
            'f_mean': merged['f_chg'].mean(),
            'f_median': merged['f_chg'].median(),
            'd_mean': merged['d_chg'].mean(),
            'd_median': merged['d_chg'].median(),
            'count': len(merged)
        }
        results.append(res)
        
        if res['f_mean'] > 2.0:
            print(f"  WARNING: High FII Change detected. Top 5 outliers:")
            top_outliers = merged.sort_values('f_chg', ascending=False).head(5)
            for _, o in top_outliers.iterrows():
                print(f"    {o['isin']}: {o['f_chg']:.2f}% (Curr: {o['fii_holding_pct_curr']:.2f}, Prev: {o['fii_holding_pct_prev']:.2f})")
        
    df_res = pd.DataFrame(results).set_index('date')
    print("\nSummary Statistics:")
    print(df_res.tail(10))
    
    # Plotting
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True)
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#0d1117')
    ax2.set_facecolor('#0d1117')
    
    # Mean Changes
    ax1.plot(df_res.index, df_res['p_mean'], marker='o', label='Promoter Mean Δ%', color='#6bcb77')
    ax1.plot(df_res.index, df_res['f_mean'], marker='s', label='FII Mean Δ%', color='#4cc9f0')
    ax1.plot(df_res.index, df_res['d_mean'], marker='^', label='DII Mean Δ%', color='#f72585')
    ax1.set_title("Average Quarterly Ownership Change % (Top 1000 Universe)", fontsize=16, color='white')
    ax1.set_ylabel("Mean Change %", color='#aaaaaa')
    ax1.grid(True, color='#222222', alpha=0.5)
    ax1.legend()
    
    # Median Changes
    ax2.plot(df_res.index, df_res['p_median'], marker='o', label='Promoter Median Δ%', color='#6bcb77')
    ax2.plot(df_res.index, df_res['f_median'], marker='s', label='FII Median Δ%', color='#4cc9f0')
    ax2.plot(df_res.index, df_res['d_median'], marker='^', label='DII Median Δ%', color='#f72585')
    ax2.set_title("Median Quarterly Ownership Change % (Top 1000 Universe)", fontsize=16, color='white')
    ax2.set_ylabel("Median Change %", color='#aaaaaa')
    ax2.grid(True, color='#222222', alpha=0.5)
    ax2.legend()
    
    # Formatting
    plt.xticks(rotation=45)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    
    out_path = REPO_ROOT / "ownership_change_vs_benchmark_v2.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    print(f"\nSaved ownership trend plot to: {out_path}")
    
    # Save CSV for reference
    df_res.to_csv(REPO_ROOT / "outputs/ownership_trends_top1000.csv")

if __name__ == "__main__":
    analyze_ownership()
