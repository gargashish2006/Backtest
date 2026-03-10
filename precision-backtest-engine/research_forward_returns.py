import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
from data.data_handler import DataHandler

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

def get_quarter_labels(signal_date, lookback_quarters):
    """Replicated quarter mapping logic."""
    year, month = signal_date.year, signal_date.month
    quarters = ["Mar", "Jun", "Sep", "Dec"]
    if month >= 2 and month < 5:    start_code, base_year = "Dec", year - 1
    elif month >= 5 and month < 8:  start_code, base_year = "Mar", year
    elif month >= 8 and month < 11: start_code, base_year = "Jun", year
    else:                           start_code, base_year = "Sep", year
    
    linear_map = {"Mar": 0, "Jun": 1, "Sep": 2, "Dec": 3}
    linear_curr = base_year * 4 + linear_map[start_code]
    linear_prev = linear_curr - lookback_quarters
    prev_code = quarters[linear_prev % 4]
    prev_year = linear_prev // 4
    return f"{start_code}-{base_year}", f"{prev_code}-{prev_year}"

def get_mc_on_date(target_date):
    available = dh.price_df[dh.price_df['date'] <= target_date]
    if available.empty: return pd.Series(dtype=float)
    latest = available['date'].max()
    return available[available['date'] == latest].set_index('isin')['mc']

def get_price_on_date(target_date):
    available = dh.price_df[dh.price_df['date'] <= target_date]
    if available.empty: return pd.Series(dtype=float)
    latest = available['date'].max()
    return available[available['date'] == latest].set_index('isin')['close']

def run_analysis():
    all_dates = sorted(dh.get_all_dates())
    # Quarterly rebalance dates: Feb/May/Aug/Nov 15th
    # We'll go from 2017 to 2022 to allow for 3Y forward returns (up to 2025/2026)
    r_dates = []
    for y in range(2017, 2023):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            # Find nearest trading day >= dt
            trading_days = [d for d in all_dates if d >= dt]
            if trading_days:
                r_dates.append(trading_days[0])
    
    results = []
    
    for reb_date in r_dates:
        print(f"Processing Rebalance Date: {reb_date.date()}...")
        signal_date = reb_date - pd.Timedelta(days=7)
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        
        # 1. Universe (Top 1000)
        universe = dh.get_universe(actual_signal_date, size=1000)
        if universe.empty: continue
        u_isins = set(universe['isin'].tolist())
        
        # 2. Forward Returns (1Y, 2Y, 3Y)
        p0 = get_price_on_date(reb_date)
        p1y = get_price_on_date(reb_date + pd.DateOffset(years=1))
        p2y = get_price_on_date(reb_date + pd.DateOffset(years=2))
        p3y = get_price_on_date(reb_date + pd.DateOffset(years=3))
        
        # 3. Predictors (SH Dec % and MCPS Inc %) for 4Q, 6Q, 8Q, 12Q
        lookbacks = [4, 6, 8, 12]
        predictors = {}
        
        sh_df = dh.shareholding_df
        mc_now = get_mc_on_date(actual_signal_date)
        
        for lb in lookbacks:
            curr_q, prev_q = get_quarter_labels(actual_signal_date, lb)
            
            # SH Decrease Signal
            curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'c_sh'})
            prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'p_sh'})
            
            if curr_sh.empty or prev_sh.empty:
                continue
                
            merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
            merged = merged[merged['isin'].isin(u_isins)]
            merged['sh_dec'] = merged['c_sh'] < merged['p_sh']
            
            # MCPS & MC Increase Signals
            mc_prev_date = actual_signal_date - pd.DateOffset(months=3 * lb)
            mc_prev = get_mc_on_date(mc_prev_date)
            
            merged['mc_now'] = merged['isin'].map(mc_now)
            merged['mc_prev'] = merged['isin'].map(mc_prev)
            merged = merged.dropna(subset=['mc_now', 'mc_prev'])
            
            merged['mc_inc'] = merged['mc_now'] > merged['mc_prev']
            merged['mcps_now'] = merged['mc_now'] / merged['c_sh']
            merged['mcps_prev'] = merged['mc_prev'] / merged['p_sh']
            merged['mcps_inc'] = merged['mcps_now'] > merged['mcps_prev']
            
            # Aggregate to Industry and Group
            merged['industry'] = merged['isin'].map(dh.isin_to_industry)
            merged['group'] = merged['isin'].map(dh.isin_to_group)
            
            ind_stats = merged.groupby('industry').agg(
                sh_dec_pct=('sh_dec', 'mean'),
                mcps_inc_pct=('mcps_inc', 'mean'),
                mc_inc_pct=('mc_inc', 'mean')
            ).reset_index()
            
            group_stats = merged.groupby('group').agg(
                g_sh_dec_pct=('sh_dec', 'mean'),
                g_mcps_inc_pct=('mcps_inc', 'mean'),
                g_mc_inc_pct=('mc_inc', 'mean')
            ).reset_index()
            
            # Store in predictors dict
            for _, row in ind_stats.iterrows():
                ind = row['industry']
                if ind not in predictors: predictors[ind] = {}
                predictors[ind][f'sh_dec_{lb}q'] = row['sh_dec_pct']
                predictors[ind][f'mcps_inc_{lb}q'] = row['mcps_inc_pct']
                predictors[ind][f'mc_inc_{lb}q'] = row['mc_inc_pct']
            
            # Map group stats back to industry level
            unique_ind_groups = merged[['industry', 'group']].drop_duplicates()
            for _, row in unique_ind_groups.iterrows():
                ind, grp = row['industry'], row['group']
                g_row = group_stats[group_stats['group'] == grp]
                if not g_row.empty:
                    if ind not in predictors: predictors[ind] = {}
                    predictors[ind][f'g_sh_dec_{lb}q'] = g_row['g_sh_dec_pct'].values[0]
                    predictors[ind][f'g_mcps_inc_{lb}q'] = g_row['g_mcps_inc_pct'].values[0]
                    predictors[ind][f'g_mc_inc_{lb}q'] = g_row['g_mc_inc_pct'].values[0]

        # 4. Industry Forward Returns
        # We only consider stocks in the Top 1000 universe at reb_date
        u_prices = pd.DataFrame({'isin': list(u_isins)})
        u_prices['p0'] = u_prices['isin'].map(p0)
        u_prices['p1y'] = u_prices['isin'].map(p1y)
        u_prices['p2y'] = u_prices['isin'].map(p2y)
        u_prices['p3y'] = u_prices['isin'].map(p3y)
        u_prices = u_prices.dropna(subset=['p0'])
        
        u_prices['ret_1y'] = (u_prices['p1y'] / u_prices['p0']) - 1
        u_prices['ret_2y'] = (u_prices['p2y'] / u_prices['p0']) - 1
        u_prices['ret_3y'] = (u_prices['p3y'] / u_prices['p0']) - 1
        
        u_prices['industry'] = u_prices['isin'].map(dh.isin_to_industry)
        ind_returns = u_prices.groupby('industry').agg(
            fwd_ret_1y=('ret_1y', 'mean'),
            fwd_ret_2y=('ret_2y', 'mean'),
            fwd_ret_3y=('ret_3y', 'mean')
        ).reset_index()
        
        # Combine predictors and returns
        for _, row in ind_returns.iterrows():
            ind = row['industry']
            if ind in predictors:
                record = {
                    'date': reb_date,
                    'industry': ind,
                    'fwd_ret_1y': row['fwd_ret_1y'],
                    'fwd_ret_2y': row['fwd_ret_2y'],
                    'fwd_ret_3y': row['fwd_ret_3y']
                }
                record.update(predictors[ind])
                results.append(record)

    df_results = pd.DataFrame(results)
    if df_results.empty:
        print("No results generated.")
        return

    # 5. Correlation Analysis
    pred_cols = [c for c in df_results.columns if any(x in c for x in ['sh_dec', 'mcps_inc', 'mc_inc'])]
    target_cols = ['fwd_ret_1y', 'fwd_ret_2y', 'fwd_ret_3y']
    
    corr_matrix = df_results[pred_cols + target_cols].corr(method='spearman').loc[pred_cols, target_cols]
    
    print("\nSpearman Correlation (Predictors vs Forward Returns):")
    print(corr_matrix)
    
    # 6. Heatmaps for Industry vs Group Comparison
    plt.figure(figsize=(16, 12))
    
    # Subplot 1: Industry Level
    plt.subplot(2, 1, 1)
    ind_preds = [c for c in pred_cols if not c.startswith('g_')]
    ind_corr = corr_matrix.loc[ind_preds]
    im1 = plt.imshow(ind_corr.values, cmap='RdYlGn', interpolation='nearest', vmin=-0.3, vmax=0.3)
    plt.colorbar(im1, label='Spearman Correlation')
    plt.xticks(range(len(target_cols)), target_cols)
    plt.yticks(range(len(ind_preds)), ind_preds)
    for i in range(len(ind_preds)):
        for j in range(len(target_cols)):
            plt.text(j, i, f"{ind_corr.iloc[i, j]:.2f}", ha="center", va="center")
    plt.title("Industry-Level Predictor Correlations")

    # Subplot 2: Group Level
    plt.subplot(2, 1, 2)
    grp_preds = [c for c in pred_cols if c.startswith('g_')]
    grp_corr = corr_matrix.loc[grp_preds]
    im2 = plt.imshow(grp_corr.values, cmap='RdYlGn', interpolation='nearest', vmin=-0.3, vmax=0.3)
    plt.colorbar(im2, label='Spearman Correlation')
    plt.xticks(range(len(target_cols)), target_cols)
    plt.yticks(range(len(grp_preds)), grp_preds)
    for i in range(len(grp_preds)):
        for j in range(len(target_cols)):
            plt.text(j, i, f"{grp_corr.iloc[i, j]:.2f}", ha="center", va="center")
    plt.title("Industry Group-Level Predictor Correlations")

    plt.tight_layout()
    plt.savefig(repo_root / "industry_vs_group_correlations.png")
    
    # 7. Bucket Analysis: Top Quartile vs Median
    best_pred = corr_matrix.mean(axis=1).idxmax()
    print(f"\nAnalyzing performance of top industries based on: {best_pred}")
    
    try:
        df_results['quartile'] = df_results.groupby('date')[best_pred].transform(
            lambda x: pd.qcut(x, 4, labels=False, duplicates='drop') if len(x.unique()) >= 2 else None
        )
        bucket_perf = df_results.groupby('quartile')[target_cols].mean()
        print("\nAverage Forward Returns by Signal Quartile (3=Best, 0=Worst):")
        print(bucket_perf)
    except Exception as e:
        print(f"Bucket analysis failed: {e}")

if __name__ == "__main__":
    run_analysis()
