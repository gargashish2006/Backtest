import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def research_industry_signals():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Nov 2024 Rebalance Date
    reb_date = pd.Timestamp("2024-11-14")
    
    # Instantiate Strategy
    strategy = ContrarianBreadthStrategy(dh, num_stocks=15)

    # REPLICATE LOGIC to capture internal state
    calc_date = reb_date - pd.Timedelta(days=7)
    all_dates = dh.get_all_dates()
    actual_calc_date = max([d for d in all_dates if d <= calc_date])
    actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])

    # Bench Return
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1

    # Shareholder Trend
    sh_trend = dh.get_shareholder_trend(reb_date, lookback_quarters=4)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)

    # (i) Industry Group Filter
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    num_to_pick = max(1, int(len(group_stats) * strategy.industry_group_top_pct))
    top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)
    
    # (ii) Industry Filter
    ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups['group'])]
    ind_stats = ind_in_groups.groupby(['group', 'industry'])['decreased'].agg(['mean', 'count']).reset_index()
    qualified_ind_stats = ind_stats[ind_stats['mean'] >= strategy.industry_decrease_min_pct]

    # (iii) RSNP Calculation
    def get_robust_map(target_date):
        window = [d for d in all_dates if d <= target_date][-30:]
        subset = dh.price_df[dh.price_df['date'].isin(window)]
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
    
    p_end_map = get_robust_map(actual_calc_date)
    p_start_map = get_robust_map(actual_lookback_start)

    industry_details = []
    for _, row in qualified_ind_stats.iterrows():
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
        
        # Get group level stats for this industry
        grp_row = top_groups[top_groups['group'] == row['group']].iloc[0]
        
        industry_details.append({
            'group': row['group'],
            'industry': ind,
            'group_decrease_pct': grp_row['mean'],
            'industry_decrease_pct': row['mean'],
            'rsnp': rsnp,
            'qualified': rsnp >= strategy.rsnp_threshold
        })

    # Report
    df = pd.DataFrame(industry_details)
    df = df.sort_values(['rsnp', 'industry_decrease_pct'], ascending=False)
    
    print(f"\nINDUSTRY SIGNALS FOR REBALANCE: {reb_date.strftime('%Y-%m-%d')}")
    print("="*140)
    header = f"{'Industry Group':<25} | {'Industry':<30} | {'Group Decr %':>12} | {'Ind Decr %':>12} | {'RSNP Score':>10} | {'Status'}"
    print(header)
    print("-" * 140)
    
    for _, row in df.iterrows():
        status = "PASSED" if row['qualified'] else "FAILED (RSNP)"
        print(f"{row['group']:<25} | {row['industry']:<30} | {row['group_decrease_pct']:>11.1%} | {row['industry_decrease_pct']:>11.1%} | {row['rsnp']:>10.2f} | {status}")
    print("="*140)

if __name__ == "__main__":
    research_industry_signals()
