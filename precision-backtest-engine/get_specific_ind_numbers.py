
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler

import warnings
warnings.filterwarnings('ignore')

def get_specific_industry_numbers(target_ind_name, date_str):
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    calc_date = pd.Timestamp(date_str)
    all_dates = dh.get_all_dates()
    actual_calc_date = max([d for d in all_dates if d <= calc_date])
    actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])

    # 1. Shareholder Data
    sh_data = dh.shareholding_df.copy()
    if 'date' not in sh_data.columns:
        sh_data['date'] = pd.to_datetime(sh_data['quarter'])
    
    valid_sh = sh_data[sh_data['date'] <= actual_calc_date].copy()
    valid_sh = valid_sh.sort_values(['isin', 'date'], ascending=[True, False])
    recent_sh = valid_sh.groupby('isin').head(5).copy()
    recent_sh['prev_sh_held'] = recent_sh.groupby('isin')['total_shareholders'].shift(-1)
    recent_sh['is_decrease'] = recent_sh['total_shareholders'] < recent_sh['prev_sh_held']
    
    isin_score = recent_sh.dropna(subset=['prev_sh_held']).groupby('isin')['is_decrease'].sum().reset_index()
    isin_score.columns = ['isin', 'decrease_count']
    
    # Mapping
    isin_score['group'] = isin_score['isin'].map(dh.isin_to_group)
    isin_score['industry'] = isin_score['isin'].map(dh.isin_to_industry)
    
    # 2. Industry Group Stats
    group_stats = isin_score.groupby('group')['decrease_count'].agg(['sum', 'count']).reset_index()
    group_stats['score_pct'] = group_stats['sum'] / (group_stats['count'] * 4)
    group_stats['rank_pct'] = group_stats['score_pct'].rank(pct=True)
    
    # 3. Industry Stats
    ind_stats = isin_score.groupby('industry')['decrease_count'].agg(['sum', 'count']).reset_index()
    ind_stats['score_pct'] = ind_stats['sum'] / (ind_stats['count'] * 4)
    ind_stats['group_name'] = ind_stats['industry'].map(lambda x: isin_score[isin_score['industry']==x]['group'].iloc[0])
    
    # 4. RSNP
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1

    def get_prices_map(target_date):
        window = [d for d in all_dates if d <= target_date][-30:]
        subset = dh.price_df[dh.price_df['date'].isin(window)]
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
    
    p_end_map = get_prices_map(actual_calc_date)
    p_start_map = get_prices_map(actual_lookback_start)

    # Find the target
    matches = ind_stats[ind_stats['industry'].str.contains(target_ind_name, case=False, na=False)]
    
    if matches.empty:
        print(f"No industry found matching '{target_ind_name}'")
        return

    results = []
    for _, row in matches.iterrows():
        ind = row['industry']
        ind_isins = [isin for isin, name in dh.isin_to_industry.items() if name == ind]
        wins, eligible = 0, 0
        for isin in ind_isins:
            p1, p0 = p_end_map.get(isin), p_start_map.get(isin)
            if p1 and p0 and p0 > 0:
                eligible += 1
                if (p1/p0 - 1) > bench_return: wins += 1
        
        rsnp = wins/eligible if eligible > 0 else 0
        grp_info = group_stats[group_stats['group'] == row['group_name']].iloc[0]
        
        results.append({
            'Industry': ind,
            'Group': row['group_name'],
            'Group Score %': f"{grp_info['score_pct']:.1%}",
            'Group Rank (Pct)': f"{grp_info['rank_pct']:.1%}",
            'Ind Score %': f"{row['score_pct']:.1%}",
            'RSNP': f"{rsnp:.2f}"
        })
    
    print(pd.DataFrame(results).to_string(index=False))

if __name__ == "__main__":
    get_specific_industry_numbers("Iron & Steel", "2026-02-05")
