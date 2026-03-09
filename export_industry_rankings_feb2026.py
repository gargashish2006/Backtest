import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.cs15_strategy import CS15Strategy
from strategies.mcps15_strategy import MCPS15Strategy

def export_rankings():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    rebalance_date = pd.Timestamp("2026-02-15")
    
    # --- CS15 Industry Rankings (Unfiltered) ---
    print("Calculating UNFILTERED CS15 Industry Rankings...")
    signal_date = rebalance_date - pd.Timedelta(days=7)
    all_dates = dh.get_all_dates()
    actual_signal_date = max([d for d in all_dates if d <= signal_date])
    actual_lookback_start = max([d for d in all_dates if d <= (actual_signal_date - pd.DateOffset(years=1))])

    sh_trend = dh.get_shareholder_trend(actual_signal_date, lookback_quarters=4)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    # Skip Group and Industry breadth filters as requested
    ind_stats = sh_trend.groupby('industry')['decreased'].mean().reset_index()
    all_industries = ind_stats['industry'].tolist()

    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_signal_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    def get_map(d):
        w = [x for x in all_dates if x <= d][-30:]
        return dh.price_df[dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()
    p1 = get_map(actual_signal_date)
    p0 = get_map(actual_lookback_start)
    
    cs15_industry_rsnp = []
    for ind in all_industries:
        if pd.isna(ind): continue
        isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
        wins, total = 0, 0
        for i in isins:
            c1, c0 = p1.get(i), p0.get(i)
            if c1 and c0 and c0 > 0:
                total += 1
                if (c1/c0 - 1) > bench_return: wins += 1
        if total > 0: 
            cs15_industry_rsnp.append({
                'Industry': ind, 
                'RSNP': wins/total, 
                'Decreased_SH_Pct': ind_stats[ind_stats['industry'] == ind]['decreased'].values[0]
            })
            
    df_cs15 = pd.DataFrame(cs15_industry_rsnp).sort_values('RSNP', ascending=False)

    # --- MCPS12 Industry Rankings (Unfiltered) ---
    print("Calculating UNFILTERED MCPS12 Industry Rankings...")
    strat_mcps = MCPS15Strategy(dh, num_stocks=12)
    s_curr_q, s_prev_q = strat_mcps._get_quarter_labels(actual_signal_date, 4)

    def get_sh_merged(curr_q, prev_q, suffix):
        sh_df = dh.shareholding_df
        curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': f'curr_sh_{suffix}'})
        prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': f'prev_sh_{suffix}'})
        if curr_sh.empty or prev_sh.empty: return pd.DataFrame()
        m = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        return m[(m[f'curr_sh_{suffix}'] > 0) & (m[f'prev_sh_{suffix}'] > 0)]

    signal_m = get_sh_merged(s_curr_q, s_prev_q, 's')
    signal_m['industry'] = signal_m['isin'].map(dh.isin_to_industry)
    signal_m = signal_m.dropna(subset=['industry'])

    mc_now  = strat_mcps._get_mc_on_date(actual_signal_date)
    mc_prev_date = actual_signal_date - pd.DateOffset(months=12)
    mc_prev = strat_mcps._get_mc_on_date(mc_prev_date)

    signal_m['mc_now']  = signal_m['isin'].map(mc_now)
    signal_m['mc_prev'] = signal_m['isin'].map(mc_prev)
    signal_m = signal_m.dropna(subset=['mc_now', 'mc_prev'])
    
    signal_m['mcps_now']      = signal_m['mc_now']  / signal_m['curr_sh_s']
    signal_m['mcps_prev']     = signal_m['mc_prev'] / signal_m['prev_sh_s']
    signal_m['mcps_positive'] = signal_m['mcps_now'] > signal_m['mcps_prev']

    df_mcps = (signal_m.groupby('industry')
                  .agg(MCPS_Positive_Pct=('mcps_positive', 'mean'))
                  .reset_index()
                  .sort_values('MCPS_Positive_Pct', ascending=False))

    # --- Export to Excel ---
    output_path = repo_root / "outputs/Feb2026_Industry_Rankings_Unfiltered.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        df_cs15.to_excel(writer, sheet_name='CS15_Industry_RSNP', index=False)
        df_mcps.to_excel(writer, sheet_name='MCPS12_Industry_Rankings', index=False)
    
    print(f"Unfiltered rankings exported to {output_path}")

if __name__ == "__main__":
    export_rankings()
