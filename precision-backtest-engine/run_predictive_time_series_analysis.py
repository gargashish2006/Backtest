import pandas as pd
import numpy as np
import warnings
from pathlib import Path
from data.data_handler import DataHandler

def run_comprehensive_predictive_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    warnings.filterwarnings('ignore')
    
    # 1. Define Quarterly Analysis Dates
    all_dates = dh.get_all_dates()
    analysis_dates = []
    # Using May, Aug, Nov, Feb sequence
    for year in range(2017, 2023):
        for month in [5, 8, 11, 2]:
            if year == 2017 and month == 2: continue
            if year == 2022 and month > 5: continue
            
            d_target = pd.Timestamp(year=year, month=month, day=15)
            # Find closest previous trading date
            valid = [dt for dt in all_dates if dt <= d_target]
            if valid:
                analysis_dates.append(max(valid))
    
    analysis_dates = sorted(list(set(analysis_dates)))
    print(f"Analyzing {len(analysis_dates)} dates from {analysis_dates[0].date()} to {analysis_dates[-1].date()}...")

    # Pre-mapping industry
    isin_to_ind = dh.isin_to_industry
    
    master_data = []

    for i, current_date in enumerate(analysis_dates):
        print(f"Processing {current_date.date()} ({i+1}/{len(analysis_dates)})...")
        
        # --- PREDICTORS (As of current_date) ---
        
        # A. Shareholder Patterns
        sh_trend = dh.get_shareholder_trend(current_date, lookback_quarters=4)
        if sh_trend.empty: continue
        sh_trend['industry'] = sh_trend['isin'].map(isin_to_ind)
        
        # B. MCPS Patterns
        prev_1y_date_target = current_date - pd.Timedelta(days=365)
        prev_1y_dates = [d for d in all_dates if d <= prev_1y_date_target]
        if not prev_1y_dates: continue
        prev_1y_date = max(prev_1y_dates)
        
        curr_prices = dh.get_daily_metrics(current_date)
        prev_prices = dh.get_daily_metrics(prev_1y_date)
        
        mcps_calc = pd.merge(sh_trend, curr_prices[['isin', 'mc']], on='isin')
        mcps_calc = pd.merge(mcps_calc, prev_prices[['isin', 'mc']], on='isin', suffixes=('', '_prev'))
        mcps_calc['mcps_inc'] = ((mcps_calc['mc']/mcps_calc['curr_sh']) > (mcps_calc['mc_prev']/mcps_calc['prev_sh'])).astype(int)
        
        # C. RSNP Calculation
        b_prices = dh.top_1000_bench
        b_curr = b_prices[b_prices['date'] <= current_date]['index_value'].iloc[-1]
        b_prev = b_prices[b_prices['date'] <= prev_1y_date]['index_value'].iloc[-1]
        b_ret = (b_curr / b_prev) - 1
        
        rsnp_calc = pd.merge(curr_prices[['isin', 'close']], prev_prices[['isin', 'close']], on='isin', suffixes=('_curr', '_prev'))
        rsnp_calc['ret'] = (rsnp_calc['close_curr'] / rsnp_calc['close_prev']) - 1
        rsnp_calc['beats'] = (rsnp_calc['ret'] > b_ret).astype(int)
        rsnp_calc['industry'] = rsnp_calc['isin'].map(isin_to_ind)

        # Aggregate Predictors by Industry
        sh_breadth = sh_trend.groupby('industry')['decreased'].mean()
        mcps_breadth = mcps_calc.groupby('industry')['mcps_inc'].mean()
        rsnp_breadth = rsnp_calc.groupby('industry')['beats'].mean()

        # --- FORWARD RETURNS ---
        def get_fwd_return(fwd_days):
            target = current_date + pd.Timedelta(days=fwd_days)
            fwd_dates = [d for d in all_dates if d >= target]
            if not fwd_dates: return None
            f_date = min(fwd_dates)
            fwd_prices = dh.get_daily_metrics(f_date)
            # Match current stocks to forward prices
            merged = pd.merge(curr_prices[['isin', 'close']], fwd_prices[['isin', 'close']], on='isin', suffixes=('_start', '_end'))
            merged['ret'] = (merged['close_end'] / merged['close_start']) - 1
            merged['industry'] = merged['isin'].map(isin_to_ind)
            return merged.groupby('industry')['ret'].mean()

        fwd_1q = get_fwd_return(91)
        fwd_2q = get_fwd_return(182)
        fwd_4q = get_fwd_return(365)
        fwd_2y = get_fwd_return(730)

        # Build combined industry-date DataFrame
        ind_list = sorted(list(set(isin_to_ind.values())))
        for ind in ind_list:
            if ind not in sh_breadth.index: continue
            
            row = {
                'date': current_date,
                'industry': ind,
                'sh_dec_breadth': sh_breadth.get(ind, np.nan),
                'mcps_inc_breadth': mcps_breadth.get(ind, np.nan),
                'rsnp_breadth': rsnp_breadth.get(ind, np.nan),
                'fwd_1q': fwd_1q.get(ind, np.nan) if fwd_1q is not None else np.nan,
                'fwd_2q': fwd_2q.get(ind, np.nan) if fwd_2q is not None else np.nan,
                'fwd_4q': fwd_4q.get(ind, np.nan) if fwd_4q is not None else np.nan,
                'fwd_2y': fwd_2y.get(ind, np.nan) if fwd_2y is not None else np.nan
            }
            master_data.append(row)

    df = pd.DataFrame(master_data).dropna(subset=['sh_dec_breadth', 'mcps_inc_breadth'])
    
    # 5. Correlation Analysis
    fwd_horizons = ['fwd_1q', 'fwd_2q', 'fwd_4q', 'fwd_2y']
    predictors = ['sh_dec_breadth', 'mcps_inc_breadth', 'rsnp_breadth']
    
    corr_matrix = df[predictors + fwd_horizons].corr()
    fwd_corrs = corr_matrix.loc[predictors, fwd_horizons]
    
    print("\n" + "="*70)
    print("PREDICTIVE POWER: CORRELATION MATRIX (Industry Level)")
    print("="*70)
    print(fwd_corrs.to_string())
    print("="*70)
    
    # Suggesting optimal prediction
    print("\n--- Summary of Findings ---")
    for fwd in fwd_horizons:
        best_pred = fwd_corrs[fwd].idxmax()
        best_val = fwd_corrs[fwd].max()
        print(f"For {fwd}: Best predictor is '{best_pred}' (Corr: {best_val:.3f})")

if __name__ == "__main__":
    run_comprehensive_predictive_analysis()
