import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def debug_aug_2025():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    date = pd.Timestamp("2025-08-14")
    calc_date = date - pd.Timedelta(days=7)
    actual_calc_date = max([d for d in dh.get_all_dates() if d <= calc_date])
    actual_lookback_start = max([d for d in dh.get_all_dates() if d <= (actual_calc_date - pd.Timedelta(days=365))])
    
    sh_trend = dh.get_shareholder_trend(date)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    num_to_pick = int(len(group_stats) * 0.5)
    top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
    
    print(f"Top 50% Groups include 'Construction'? {'Construction' in top_groups}")
    
    ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
    ind_stats = ind_in_groups.groupby('industry')['decreased'].mean().reset_index()
    qualified_industries = ind_stats[ind_stats['decreased'] >= 0.50]['industry'].tolist()
    
    print(f"Qualified Industries count: {len(qualified_industries)}")
    print(f"Is 'Civil Construction' qualified? {'Civil Construction' in qualified_industries}")
    
    # RSNP
    b_end = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    prices_sub = dh.price_df[dh.price_df['date'].isin([actual_calc_date, actual_lookback_start])]
    p_map = prices_sub.groupby(['isin', 'date'])['close'].first().to_dict()
    
    industry_rsnp = []
    for ind in qualified_industries:
        ind_isins = [isin for isin, name in dh.isin_to_industry.items() if name == ind]
        wins = 0
        eligible = 0
        for isin in ind_isins:
            p1 = p_map.get((isin, actual_calc_date))
            p0 = p_map.get((isin, actual_lookback_start))
            if p1 and p0:
                eligible += 1
                if (p1/p0 - 1) > bench_return:
                    wins += 1
        if eligible > 0:
            industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
            
    ind_ranked = pd.DataFrame(industry_rsnp).sort_values('rsnp', ascending=False)
    print("\n--- Industry Rankings ---")
    print(ind_ranked.head(30))
    
if __name__ == "__main__":
    debug_aug_2025()
