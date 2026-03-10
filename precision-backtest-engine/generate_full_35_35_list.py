import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_full_35_35_industry_list():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    date = pd.Timestamp("2026-02-05") # Latest available
    all_dates = dh.get_all_dates()
    
    print(f"Generating Full 35/35 Industry Rankings based on {date.date()}...")
    
    # 1. Shareholder Breadth (8Q)
    sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
    if sh_trend.empty:
        print("No shareholder data found.")
        return
    
    # 2. Universe (Top 1000)
    univ = dh.get_universe(date, size=1000)
    univ_isins = set(univ['isin'].tolist())
    
    # 3. RSNP calculation (1Q = 90d lookback)
    q_ago_date = max([d for d in all_dates if d <= date - pd.Timedelta(days=90)])
    prices = dh.get_daily_prices(date)
    prev_p = dh.get_daily_prices(q_ago_date)
    
    common = set(prices.keys()) & set(prev_p.keys()) & univ_isins
    rets = {isin: (prices[isin]/prev_p[isin]) - 1 for isin in common}
    bench_median = pd.Series(list(rets.values())).median()
    
    stocks_info = []
    for isin in common:
        if isin in dh.isin_to_group and isin in dh.isin_to_industry:
            stocks_info.append({
                'isin': isin,
                'group': dh.isin_to_group[isin],
                'industry': dh.isin_to_industry[isin],
                'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0] if isin in sh_trend['isin'].values else False,
                'beats_bench': rets[isin] > bench_median
            })
    
    df_info = pd.DataFrame(stocks_info)
    
    # 4. Group Top 35%
    group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
    top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
    
    # 5. Industry Top 35% within Top Groups (BREADTH FIRST)
    rel_df = df_info[df_info['group'].isin(top_groups)]
    ind_stats = rel_df.groupby('industry').agg({
        'decreased': 'mean',
        'beats_bench': 'mean' 
    }).sort_values('decreased', ascending=False)
    
    # Take top 35% by breadth
    top_ind_b = ind_stats.head(max(1, int(len(ind_stats) * 0.35)))
    
    # Now sort the survivors by RSNP for the report (Reverse RSNP)
    final_rankings = top_ind_b.sort_values(['beats_bench', 'decreased'], ascending=[True, False])
    
    # Export
    output_path = repo_root / "outputs/Feb_2026_Full_35_35_RSNP_Rankings.xlsx"
    final_rankings.to_excel(output_path)
    
    print(f"\nSuccessfully generated rankings for {len(final_rankings)} industries.")
    print(f"File saved to: {output_path}")
    
    print("\nIndustries (Ranked by Reverse RSNP):")
    print("-" * 60)
    print(f"{'Industry':<40} | {'RSNP':<10} | {'Breadth':<10}")
    print("-" * 60)
    for ind, row in final_rankings.iterrows():
        print(f"{ind:<40} | {row['beats_bench']:<10.2f} | {row['decreased']:<10.2f}")

if __name__ == "__main__":
    generate_full_35_35_industry_list()
