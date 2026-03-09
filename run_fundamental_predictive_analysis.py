import pandas as pd
import numpy as np
import warnings
from pathlib import Path
from data.data_handler import DataHandler

def run_fundamental_balanced_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    warnings.filterwarnings('ignore')
    all_dates = dh.get_all_dates()

    # 1. Setup Rebalance Dates (The anchor for Action and Forward Returns)
    rebalance_dates = []
    for year in range(2017, 2023):
        for month in [5, 8, 11, 2]:
            if year == 2017 and month == 2: continue
            if year == 2022 and month > 5: continue
            d_target = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d_target]
            if valid: rebalance_dates.append(max(valid))
    rebalance_dates = sorted(list(set(rebalance_dates)))

    # 2. Quarter Mapping Helper
    def get_signal_dates(rebalance_date):
        m = rebalance_date.month
        y = rebalance_date.year
        if m == 5: # May -> Mar
            curr_q_code, curr_q_date = f"Mar-{y}", pd.Timestamp(year=y, month=3, day=31)
            prev_q_code, prev_q_date = f"Mar-{y-1}", pd.Timestamp(year=y-1, month=3, day=31)
        elif m == 8: # Aug -> Jun
            curr_q_code, curr_q_date = f"Jun-{y}", pd.Timestamp(year=y, month=6, day=30)
            prev_q_code, prev_q_date = f"Jun-{y-1}", pd.Timestamp(year=y-1, month=6, day=30)
        elif m == 11: # Nov -> Sep
            curr_q_code, curr_q_date = f"Sep-{y}", pd.Timestamp(year=y, month=9, day=30)
            prev_q_code, prev_q_date = f"Sep-{y-1}", pd.Timestamp(year=y-1, month=9, day=30)
        else: # Feb -> Dec (Previous Year)
            curr_q_code, curr_q_date = f"Dec-{y-1}", pd.Timestamp(year=y-1, month=12, day=31)
            prev_q_code, prev_q_date = f"Dec-{y-2}", pd.Timestamp(year=y-2, month=12, day=31)
        
        # Align to closest trading dates
        curr_trade_date = max([d for d in all_dates if d <= curr_q_date])
        prev_trade_date = max([d for d in all_dates if d <= prev_q_date])
        return curr_q_code, curr_trade_date, prev_q_code, prev_trade_date

    master_data = []

    for rb_date in rebalance_dates:
        curr_q, curr_sig_date, prev_q, prev_sig_date = get_signal_dates(rb_date)
        print(f"RB: {rb_date.date()} | Signal Date: {curr_sig_date.date()}")

        # --- A. Predictors (Snapshots on Signal Dates) ---
        df_sh = dh.shareholding_df
        curr_sh = df_sh[df_sh['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr_sh'})
        prev_sh = df_sh[df_sh['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev_sh'})
        
        sh_merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        sh_merged['sh_dec'] = (sh_merged['curr_sh'] < sh_merged['prev_sh']).astype(int)
        
        # MCPS: Use MC on the SAME date as signal (curr_sig_date and prev_sig_date)
        curr_prices = dh.get_daily_metrics(curr_sig_date)
        prev_prices = dh.get_daily_metrics(prev_sig_date)
        
        mcps_calc = pd.merge(sh_merged, curr_prices[['isin', 'mc']], on='isin')
        mcps_calc = pd.merge(mcps_calc, prev_prices[['isin', 'mc']], on='isin', suffixes=('', '_prev'))
        mcps_calc['mcps_inc'] = ((mcps_calc['mc']/mcps_calc['curr_sh']) > (mcps_calc['mc_prev']/mcps_calc['prev_sh'])).astype(int)
        
        # RSNP: Strength up to Signal Date vs 1Y ago
        b_prices = dh.top_1000_bench
        b_curr = b_prices[b_prices['date'] <= curr_sig_date]['index_value'].iloc[-1]
        b_prev = b_prices[b_prices['date'] <= prev_sig_date]['index_value'].iloc[-1]
        b_ret = (b_curr / b_prev) - 1
        
        rsnp_calc = pd.merge(curr_prices[['isin', 'close']], prev_prices[['isin', 'close']], on='isin', suffixes=('_curr', '_prev'))
        rsnp_calc['ret'] = (rsnp_calc['close_curr'] / rsnp_calc['close_prev']) - 1
        rsnp_calc['beats'] = (rsnp_calc['ret'] > b_ret).astype(int)

        # Aggregate predictors by industry
        isin_to_ind = dh.isin_to_industry
        sh_merged['industry'] = sh_merged['isin'].map(isin_to_ind)
        mcps_calc['industry'] = mcps_calc['isin'].map(isin_to_ind)
        rsnp_calc['industry'] = rsnp_calc['isin'].map(isin_to_ind)

        ind_sh_breadth = sh_merged.groupby('industry')['sh_dec'].mean()
        ind_mcps_breadth = mcps_calc.groupby('industry')['mcps_inc'].mean()
        ind_rsnp_breadth = rsnp_calc.groupby('industry')['beats'].mean()

        # --- B. Forward Returns (Predicting from RB Date onwards) ---
        rb_prices = dh.get_daily_metrics(rb_date)
        
        def get_fwd_return(fwd_days):
            target = rb_date + pd.Timedelta(days=fwd_days)
            fwd_dates = [d for d in all_dates if d >= target]
            if not fwd_dates: return None
            f_date = min(fwd_dates)
            f_prices = dh.get_daily_metrics(f_date)
            m = pd.merge(rb_prices[['isin', 'close']], f_prices[['isin', 'close']], on='isin', suffixes=('_start', '_end'))
            m['ret'] = (m['close_end'] / m['close_start']) - 1
            m['industry'] = m['isin'].map(isin_to_ind)
            return m.groupby('industry')['ret'].mean()

        fwd_1q = get_fwd_return(91)
        fwd_2q = get_fwd_return(182)
        fwd_4q = get_fwd_return(365)
        fwd_2y = get_fwd_return(730)

        # Aggregate Result
        all_inds = sorted(list(set(isin_to_ind.values())))
        for ind in all_inds:
            if ind not in ind_sh_breadth.index: continue
            row = {
                'date': rb_date,
                'industry': ind,
                'sh_dec_breadth': ind_sh_breadth.get(ind, 0),
                'mcps_inc_breadth': ind_mcps_breadth.get(ind, 0),
                'rsnp_breadth': ind_rsnp_breadth.get(ind, 0),
                'fwd_1q': fwd_1q.get(ind, np.nan) if fwd_1q is not None else np.nan,
                'fwd_2q': fwd_2q.get(ind, np.nan) if fwd_2q is not None else np.nan,
                'fwd_4q': fwd_4q.get(ind, np.nan) if fwd_4q is not None else np.nan,
                'fwd_2y': fwd_2y.get(ind, np.nan) if fwd_2y is not None else np.nan
            }
            master_data.append(row)

    df = pd.DataFrame(master_data).dropna()
    
    # 3. Correlation Analysis
    preds = ['sh_dec_breadth', 'mcps_inc_breadth', 'rsnp_breadth']
    fwds = ['fwd_1q', 'fwd_2q', 'fwd_4q', 'fwd_2y']
    
    corr_matrix = df[preds + fwds].corr().loc[preds, fwds]
    
    print("\n" + "="*75)
    print("STRICTLY FUNDAMENTAL PREDICTIVE POWER (Signal Date = SH Date)")
    print("="*75)
    print(corr_matrix.to_string())
    print("="*75)

if __name__ == "__main__":
    run_fundamental_balanced_analysis()
