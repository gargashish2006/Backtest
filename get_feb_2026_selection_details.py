
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def get_feb_2026_details():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # Target Date
    target_date = pd.Timestamp("2026-02-15")
    
    # Initialize Strategy
    strategy = ContrarianBreadthStrategy(dh)
    
    # --- Logic Extraction (Mirrors calculate_selection) ---
    print(f"Analyzing Selection for {target_date.date()}...\n")
    
    # 1. Calculation dates
    calc_date = target_date - pd.Timedelta(days=7)
    all_dates = dh.get_all_dates()
    actual_calc_date = max([d for d in all_dates if d <= calc_date])
    actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
    
    print(f"Calculation Date: {actual_calc_date.date()}")
    print(f"Lookback Start : {actual_lookback_start.date()}\n")

    # 2. Shareholder Trends
    sh_trend = dh.get_shareholder_trend(target_date, lookback_quarters=4)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    # (i) Group Scores
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    group_stats = group_stats.sort_values('mean', ascending=False)
    
    # Filter Top 50% Groups
    num_to_pick = max(1, int(len(group_stats) * 0.50))
    top_groups = group_stats.head(num_to_pick)['group'].tolist()
    
    # Map Group Scores for display
    group_score_map = dict(zip(group_stats['group'], group_stats['mean']))

    # (ii) Industry Scores
    ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
    ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    
    # Filter High Breadth Industries (>50%)
    qualified_inds = ind_stats[ind_stats['mean'] >= 0.50].copy()
    qualified_ind_list = qualified_inds['industry'].tolist()
    
    # Map Industry Scores
    ind_score_map = dict(zip(qualified_inds['industry'], qualified_inds['mean']))
    
    # (iii) RSNP Calculation
    # Benchmark Return
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    # Price Maps
    def get_robust_map(t_date):
        window = [d for d in all_dates if d <= t_date][-30:]
        subset = dh.price_df[dh.price_df['date'].isin(window)]
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
    
    p_end_map = get_robust_map(actual_calc_date)
    p_start_map = get_robust_map(actual_lookback_start)
    
    industry_rsnp = []
    for ind in qualified_ind_list:
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
        
        if eligible > 0:
            rsnp = wins/eligible
            if rsnp >= 0.40: # RSNP Threshold
                 # Get Group for this Industry
                 grp = dh.isin_to_group.get(ind_isins[0], "Unknown")
                 industry_rsnp.append({
                     'Industry': ind,
                     'Group': grp,
                     'Group_Score_Pct': group_score_map.get(grp, 0) * 100,
                     'Industry_Score_Pct': ind_score_map.get(ind, 0) * 100,
                     'RSNP_Score': rsnp
                 })
    
    # Output Table
    if not industry_rsnp:
        print("No industries qualified.")
        return

    df = pd.DataFrame(industry_rsnp)
    df = df.sort_values('RSNP_Score', ascending=False)
    
    print("="*100)
    print(f"{'Industry':<35} | {'Group':<30} | {'Grp Score':<10} | {'Ind Score':<10} | {'RSNP':<6}")
    print("-" * 100)
    
    for _, row in df.iterrows():
        print(f"{row['Industry']:<35} | {row['Group']:<30} | {row['Group_Score_Pct']:>9.1f}% | {row['Industry_Score_Pct']:>9.1f}% | {row['RSNP_Score']:>6.2f}")
    print("="*100)

if __name__ == "__main__":
    get_feb_2026_details()
