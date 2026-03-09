import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def generate_feb_2026_score_report():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Config (Champion Model)
    group_top_pct = 0.50
    ind_min_pct = 0.50
    rsnp_min = 0.40
    target_date = pd.Timestamp("2026-02-05")
    
    # Logic replication from ContrarianBreadthStrategy
    # 1. Shareholder Data
    sh_trend = dh.get_shareholder_trend(target_date)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    # (i) Group Scores
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    num_to_pick = max(1, int(len(group_stats) * group_top_pct))
    top_groups_df = group_stats.sort_values('mean', ascending=False).head(num_to_pick)
    top_groups = top_groups_df['group'].tolist()
    
    # (ii) Industry Scores (within top groups)
    ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
    ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    qualified_ind_df = ind_stats[ind_stats['mean'] >= ind_min_pct]
    qualified_industries = qualified_ind_df['industry'].tolist()
    
    # (iii) RSNP Calculation
    calc_date = target_date - pd.Timedelta(days=7)
    all_dates = dh.get_all_dates()
    all_trading_dates = all_dates
    actual_calc_date = max([d for d in all_trading_dates if d <= calc_date])
    actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
    
    b_end = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    def get_robust_map(target_date):
        window = [d for d in all_dates if d <= target_date][-30:]
        subset = dh.price_df[dh.price_df['date'].isin(window)]
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
    
    p_end_map = get_robust_map(actual_calc_date)
    p_start_map = get_robust_map(actual_lookback_start)
    
    final_rows = []
    
    # Group Mapping for easy lookup
    group_score_map = dict(zip(group_stats['group'], group_stats['mean']))
    ind_to_group_map = {row['industry']: row['group'] for _, row in sh_trend.drop_duplicates('industry').iterrows()}
    
    for ind in qualified_industries:
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
        
        rsnp_score = wins/eligible if eligible > 0 else 0
        
        # Only keep if RSNP meets threshold
        if rsnp_score >= rsnp_min:
            group_name = ind_to_group_map.get(ind, "Unknown")
            final_rows.append({
                'Industry': ind,
                'Industry_Group': group_name,
                'Industry_Score_(SH_Dec_%)': f"{ind_stats[ind_stats['industry']==ind]['mean'].values[0]*100:.2f}%",
                'Group_Score_(SH_Dec_%)': f"{group_score_map.get(group_name, 0)*100:.2f}%",
                'RSNP_Score_(Breadth)': f"{rsnp_score:.4f}"
            })
            
    df_output = pd.DataFrame(final_rows)
    df_output = df_output.sort_values('RSNP_Score_(Breadth)', ascending=False)
    
    output_path = "/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/outputs/feb_2026_industry_diagnostic.csv"
    df_output.to_csv(output_path, index=False)
    print(f"Diagnostic report generated for Feb 2026.")
    print(df_output.to_string(index=False))

if __name__ == "__main__":
    generate_feb_2026_score_report()
