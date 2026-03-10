import pandas as pd
import numpy as np
import warnings
from pathlib import Path
from data.data_handler import DataHandler

def predictive_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup Dates
    all_dates = dh.get_all_dates()
    start_date = pd.Timestamp('2017-05-15')
    end_date = pd.Timestamp('2020-05-15')
    
    # Align to actual trading dates
    start_date = max([d for d in all_dates if d <= start_date])
    end_date = max([d for d in all_dates if d <= end_date])
    
    # 2. Calculate Forward Industry Returns (May 2017 -> May 2020)
    start_prices = dh.get_daily_metrics(start_date)
    end_prices = dh.get_daily_metrics(end_date)
    
    price_merged = pd.merge(
        start_prices[['isin', 'close', 'mc']], 
        end_prices[['isin', 'close']], 
        on='isin', suffixes=('_start', '_end')
    )
    price_merged['fwd_return'] = (price_merged['close_end'] / price_merged['close_start']) - 1
    price_merged['industry'] = price_merged['isin'].map(dh.isin_to_industry)
    
    ind_fwd_returns = price_merged.groupby('industry')['fwd_return'].mean()
    
    # 3. Calculate Predictive Signals (As of May 2017)
    # A. Shareholder Decrease Breadth (4Q lookback at start_date)
    sh_trend = dh.get_shareholder_trend(start_date, lookback_quarters=4)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    ind_sh_breadth = sh_trend.groupby('industry')['decreased'].mean() # % of stocks with decreasing SH
    
    # B. MCPS Increase Breadth
    # Need mcps 4Q ago vs start_date
    prev_4q_date_target = start_date - pd.Timedelta(days=365)
    prev_4q_date = max([d for d in all_dates if d <= prev_4q_date_target])
    prev_prices = dh.get_daily_metrics(prev_4q_date)
    
    mcps_calc = pd.merge(sh_trend, start_prices[['isin', 'mc']], on='isin')
    mcps_calc = pd.merge(mcps_calc, prev_prices[['isin', 'mc']], on='isin', suffixes=('', '_prev'))
    
    mcps_calc['curr_mcps'] = mcps_calc['mc'] / mcps_calc['curr_sh']
    mcps_calc['prev_mcps'] = mcps_calc['mc_prev'] / mcps_calc['prev_sh']
    mcps_calc['mcps_inc'] = (mcps_calc['curr_mcps'] > mcps_calc['prev_mcps']).astype(int)
    ind_mcps_breadth = mcps_calc.groupby('industry')['mcps_inc'].mean()
    
    # C. Industry RSNP (Trailing 1Y vs Benchmark at start_date)
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= start_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= prev_4q_date]['index_value'].iloc[-1]
    b_ret = (b_end / b_start) - 1
    
    start_prices['industry'] = start_prices['isin'].map(dh.isin_to_industry)
    rsnp_calc = pd.merge(start_prices[['isin', 'close', 'industry']], prev_prices[['isin', 'close']], on='isin', suffixes=('_curr', '_prev'))
    rsnp_calc['ret_1y'] = (rsnp_calc['close_curr'] / rsnp_calc['close_prev']) - 1
    rsnp_calc['beats'] = (rsnp_calc['ret_1y'] > b_ret).astype(int)
    ind_rsnp = rsnp_calc.groupby('industry')['beats'].mean()
    
    # 4. Final Aggregation & Correlation
    analysis = pd.DataFrame({
        'Fwd_Return': ind_fwd_returns,
        'SH_Dec_Breadth': ind_sh_breadth,
        'MCPS_Inc_Breadth': ind_mcps_breadth,
        'Trailing_RSNP': ind_rsnp
    }).dropna()
    
    correlations = analysis.corr()['Fwd_Return'].sort_values(ascending=False)
    
    print("\n--- Predictive Power of Metrics (Correlation with 2017-2020 Returns) ---")
    print(correlations.to_string())
    
    # Show Top vs Bottom industries for SH_Dec_Breadth to see if the "Winners" had it
    print("\n--- Top Forward Returns vs SH Decrease Breadth in May 2017 ---")
    print(analysis.sort_values('Fwd_Return', ascending=False).head(10)[['Fwd_Return', 'SH_Dec_Breadth']])

if __name__ == "__main__":
    predictive_analysis()
