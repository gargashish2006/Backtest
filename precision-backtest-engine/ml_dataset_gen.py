
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler

def generate_ml_dataset():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    print("Loading data...")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # --- Vectorized Calculations ---
    # 1. Pivot Prices
    print("Pivoting prices...")
    prices = dh.price_df.pivot(index='date', columns='isin', values='close')
    
    # 2. Get Benchmark (Nifty 500)
    print("Loading Benchmark...")
    bench_path = repo_root / "benchmarks/Nifty_500/timeseries.parquet"
    if bench_path.exists():
        bench_df = pd.read_parquet(bench_path)
    else:
        bench_path = repo_root / "benchmarks/Nifty_500/timeseries.csv"
        if bench_path.exists():
            bench_df = pd.read_csv(bench_path)
        else:
            print("Warning: Nifty 500 not found. Using Top 1000 Equal Weight as proxy.")
            bench_df = dh.top_1000_bench
            
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    # Handle different column names
    if 'index_value' in bench_df.columns:
        b_series = bench_df.set_index('date')['index_value']
    elif 'close' in bench_df.columns:
        b_series = bench_df.set_index('date')['close']
    elif 'nav' in bench_df.columns:
         b_series = bench_df.set_index('date')['nav']
    else:
        raise ValueError("Benchmark format unknown")
        
    b_series = b_series.sort_index()
    
    # Align Benchmark to Dates
    b_series = b_series.reindex(prices.index).ffill()
    
    # 3. Calculate RSNP (Vectorized)
    print("Calculating RSNP...")
    # Ratio = Stock / Benchmark
    rel_strength = prices.div(b_series, axis=0)
    
    # ROC of Ratio (Percentage change of relative strength)
    # 6M = 126 days, 1Y = 252 days, 2Y = 504 days
    rsnp_6m = rel_strength.pct_change(periods=126)
    rsnp_1y = rel_strength.pct_change(periods=252)
    rsnp_2y = rel_strength.pct_change(periods=504)
    
    # 4. Calculate Forward Returns (Target)
    # 3 Months = 63 trading days
    # Return at time t is (Price_t+63 / Price_t) - 1
    # We use shift(-63) to bring future return to current row
    print("Calculating Targets...")
    future_returns_3m = prices.pct_change(periods=63).shift(-63)
    
    # --- Event Loop for Shareholder Data ---
    # Shareholder data is sparse (quarterly), so we still loop or merge.
    # We generate the dataset at Rebalance Dates.
    
    start_date = pd.Timestamp("2017-05-15")
    end_date = pd.Timestamp("2022-11-15")
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    
    for year in range(2017, 2023):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if start_date <= reb <= end_date:
                    rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))
    
    dataset = []
    print(f"Aggregating features for {len(rebalance_dates)} quarters...")
    
    for i, date in enumerate(rebalance_dates):
        print(f"Processing {date.date()} ({i+1}/{len(rebalance_dates)})")
        
        # 1. Universe: Top 1000 Liquid by Market Cap
        metrics = dh.get_daily_metrics(date)
        if metrics.empty: continue
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        isins = universe['isin'].tolist()
        
        # 2. Get Shareholder Trends
        trend_4q = dh.get_shareholder_trend(date, lookback_quarters=4)
        trend_6q = dh.get_shareholder_trend(date, lookback_quarters=6)
        trend_8q = dh.get_shareholder_trend(date, lookback_quarters=8)
        
        map_4q = dict(zip(trend_4q['isin'], trend_4q['decreased'].astype(int))) if not trend_4q.empty else {}
        map_6q = dict(zip(trend_6q['isin'], trend_6q['decreased'].astype(int))) if not trend_6q.empty else {}
        map_8q = dict(zip(trend_8q['isin'], trend_8q['decreased'].astype(int))) if not trend_8q.empty else {}
        
        # 3. Retrieve Vectorized Features
        # We need values at `date` for the specific ISINs
        # Efficient lookup using .loc[date, isins]
        
        # Ensure date is in index (it should be as it comes from all_dates)
        if date not in prices.index: continue
        
        r6 = rsnp_6m.loc[date, isins]
        r1 = rsnp_1y.loc[date, isins]
        r2 = rsnp_2y.loc[date, isins]
        tgt = future_returns_3m.loc[date, isins]
        
        # --- Industry and Group Features (V2) ---
        # Map Industry/Group info to ISINs
        # metrics already has 'ind' and 'group' columns? Need to check DataHandler or assume they exist.
        # DataHandler.get_daily_metrics() usually returns 'ind' and 'group'.
        
        # We need to compute features for the UNIVERSE (Top 1000) to avoid noise from illiquid micro-caps
        
        # 1. Enrich Universe with RSNP and Shareholder Decrease cols
        # We have lists/dicts, map them to a temporary DF
        
        # FIX: Manually map industry info (DataHandler doesn't include it in daily_metrics)
        universe = universe.copy() # Avoid SettingWithCopyWarning
        universe['ind'] = universe['isin'].map(dh.isin_to_industry).fillna('Unknown')
        universe['group'] = universe['isin'].map(dh.isin_to_group).fillna('Unknown')
        
        # Create a DF for the current 1000 stocks
        u_df = universe[['isin', 'ind', 'group']].copy()
        
        # Map Shareholder Decrease (4Q is the specific signal we care about for breadth)
        u_df['sh_dec_4q'] = u_df['isin'].map(map_4q).fillna(0)
        
        # Map RSNP 1Y
        # r1 is ALREADY a Series of RSNP values for this date (index=ISIN)
        u_df['rsnp_1y'] = u_df['isin'].map(r1)
        
        # 2. Compute Aggregates
        # Industry Breadth: Mean of sh_dec_4q
        ind_breadth = u_df.groupby('ind')['sh_dec_4q'].mean()
        grp_breadth = u_df.groupby('group')['sh_dec_4q'].mean()
        
        # Industry Momentum: Mean of RSNP 1Y
        ind_mom = u_df.groupby('ind')['rsnp_1y'].mean()
        grp_mom = u_df.groupby('group')['rsnp_1y'].mean()
        
        # 3. Map back to Stock
        # Create mapping dicts
        map_ind_breadth = ind_breadth.to_dict()
        map_grp_breadth = grp_breadth.to_dict()
        map_ind_mom = ind_mom.to_dict()
        map_grp_mom = grp_mom.to_dict()
        
        # Construct Rows
        for isin in isins:
            # Skip if target is NaN
            t_val = tgt.get(isin, np.nan)
            if pd.isna(t_val): continue
            
            # Context info
            stock_ind = u_df.loc[u_df['isin'] == isin, 'ind'].iloc[0]
            stock_grp = u_df.loc[u_df['isin'] == isin, 'group'].iloc[0]
            
            row = {
                'date': date,
                'isin': isin,
                'ind': stock_ind, # Metadata
                'group': stock_grp, # Metadata
                'sh_decrease_4q_binary': map_4q.get(isin, 0),
                'sh_decrease_6q_binary': map_6q.get(isin, 0),
                'sh_decrease_8q_binary': map_8q.get(isin, 0),
                'rsnp_6m': r6.get(isin, np.nan),
                'rsnp_1y': r1.get(isin, np.nan),
                'rsnp_2y': r2.get(isin, np.nan),
                'ind_sh_breadth': map_ind_breadth.get(stock_ind, 0),
                'grp_sh_breadth': map_grp_breadth.get(stock_grp, 0),
                'ind_rsnp_1y': map_ind_mom.get(stock_ind, 0),
                'grp_rsnp_1y': map_grp_mom.get(stock_grp, 0),
                'target_3m_return': t_val
            }
            dataset.append(row)
            
    df = pd.DataFrame(dataset)
    # Drop rows where critical FEATURES are missing
    # New features shouldn't be missing if stock has industry, but RSNP might be.
    df = df.dropna(subset=['rsnp_1y', 'target_3m_return', 'ind_rsnp_1y'])
    
    output_path = repo_root / "data/ml_dataset_2017_2022_v2.csv"
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")

if __name__ == "__main__":
    generate_ml_dataset()
