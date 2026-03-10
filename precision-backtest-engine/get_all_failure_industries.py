
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def get_all_qualifying_failure_industries():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()
    
    # Target Rebalance Date: Feb 2026
    d = pd.Timestamp(year=2026, month=2, day=15)
    valid = [dt for dt in all_dates if dt <= d]
    rebalance_date = max(valid)
    
    calc_date = rebalance_date - pd.Timedelta(days=7)
    actual_calc_date = max([dt for dt in all_dates if dt <= calc_date])
    actual_lookback_start = max([dt for dt in all_dates if dt <= (actual_calc_date - pd.Timedelta(days=365))])

    print(f"Diagnostics for: {rebalance_date}")
    print(f"Calculation Date: {actual_calc_date}")

    # 1. Shareholder Trend
    sh_trend = dh.get_shareholder_trend(rebalance_date, lookback_quarters=4)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    # 2. Industry Group Selection (BOTTOM 50%)
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    
    # Bottom 50% groups
    num_total = len(group_stats)
    half = num_total // 2
    bottom_groups_df = group_stats.sort_values('mean', ascending=True).head(half)
    bottom_groups = bottom_groups_df['group'].tolist()
    
    # 3. Industry Selection (LOW BREADTH < 50%)
    sh_in_bottom = sh_trend[sh_trend['group'].isin(bottom_groups)]
    ind_stats = sh_in_bottom.groupby(['group', 'industry'])['decreased'].agg(['mean', 'count']).reset_index()
    ind_stats = ind_stats.rename(columns={'mean': 'breadth'})
    
    # Filter for Low Breadth (< 50%)
    failure_industries_df = ind_stats[ind_stats['breadth'] < 0.50].copy()
    
    # 4. RSNP Calculation (LOW < 0.40)
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    def get_robust_map(target_date):
        window = [dt for dt in all_dates if dt <= target_date][-3:]
        subset = dh.price_df[dh.price_df['date'].isin(window)]
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
    
    p_end_map = get_robust_map(actual_calc_date)
    p_start_map = get_robust_map(actual_lookback_start)
    
    final_results = []
    for _, row in failure_industries_df.iterrows():
        ind = row['industry']
        ind_isins = [isin for isin, name in dh.isin_to_industry.items() if name == ind]
        wins = 0
        eligible = 0
        for isin in ind_isins:
            p1 = p_end_map.get(isin)
            p0 = p_start_map.get(isin)
            if p1 and p0 and p0 > 0:
                eligible += 1
                if (p1/p0 - 1) > bench_return:
                    wins += 1
        
        rsnp = wins/eligible if eligible > 0 else 0
        
        # Filter for Low RSNP (< 0.40)
        if rsnp < 0.40:
            final_results.append({
                'Group': row['group'],
                'Industry': ind,
                'Breadth': f"{row['breadth']:.2%}",
                'RSNP': f"{rsnp:.4f}"
            })
            
    df_final = pd.DataFrame(final_results)
    if df_final.empty:
        print("\nNo qualifying industries.")
    else:
        print("\n" + "="*80)
        print("ALL QUALIFYING FAILURE INDUSTRIES (BOTTOM/LOW/LOW)")
        print(f"REBALANCE: {rebalance_date} | PRE-STOCK SELECTION")
        print("="*80)
        print(df_final.sort_values(['Group', 'RSNP']).to_string(index=False))
        print("="*80)
        print(f"Total: {len(df_final)}")

if __name__ == "__main__":
    get_all_qualifying_failure_industries()
