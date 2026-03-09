import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_q1_feb_2026_list():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    date = pd.Timestamp("2026-02-05") # Latest available
    all_dates = dh.get_all_dates()
    
    print(f"Generating Selection for Champion Model (Q1 35/35) on {date.date()}...")
    
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
    
    # Load Identity Mapping
    master_path = repo_root / "database/master_identifiers.csv"
    if master_path.exists():
        master_df = pd.read_csv(master_path)
        isin_to_symbol = dict(zip(master_df['isin'], master_df['nse_symbol']))
    else:
        isin_to_symbol = {}
        
    stocks_info = []
    for isin in common:
        if isin in dh.isin_to_group and isin in dh.isin_to_industry:
            stocks_info.append({
                'isin': isin,
                'symbol': isin_to_symbol.get(isin, isin),
                'name': dh.isin_to_name.get(isin, isin),
                'group': dh.isin_to_group[isin],
                'industry': dh.isin_to_industry[isin],
                'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0] if isin in sh_trend['isin'].values else False,
                'beats_bench': rets[isin] > bench_median,
                'mc': univ[univ['isin'] == isin]['mc'].values[0] if isin in univ['isin'].values else 0
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
    }).sort_values('decreased', ascending=False) # Sort by Breadth
    
    # Selection: Top 35% of these industries by BREADTH
    top_ind_b = ind_stats.head(max(1, int(len(ind_stats) * 0.35)))
    
    # 6. Q1 (Bottom 25%) RSNP Filter (among high-breadth survivors)
    sorted_rsnp = top_ind_b.sort_values('beats_bench')
    q1_inds = sorted_rsnp.head(max(1, int(len(sorted_rsnp) * 0.25))).index.tolist()
    
    print(f"\nTargeting {len(q1_inds)} Industries in Q1 (Deep Contrarian Cluster)")
    
    # 7. Final Selection
    selection = []
    for ind in q1_inds:
        istks = rel_df[rel_df['industry'] == ind].sort_values('mc', ascending=False)
        top3 = istks.head(3)
        for _, row in top3.iterrows():
            selection.append({
                'Industry': ind,
                'Group': row['group'],
                'Symbol': row['symbol'],
                'ISIN': row['isin'],
                'Market Cap (Cr)': row['mc'],
                'Industry Breadth': top_ind_b.loc[ind, 'decreased'],
                'Industry RSNP': top_ind_b.loc[ind, 'beats_bench']
            })
            
    final_df = pd.DataFrame(selection)
    output_path = repo_root / "outputs/Feb_2026_Q1_DeepContrarian_Rebalance.xlsx"
    final_df.to_excel(output_path, index=False)
    
    print(f"\nSuccessfully generated list with {len(final_df)} stocks.")
    print(f"File saved to: {output_path}")
    
    print("\nIndustries selected:")
    for ind in q1_inds:
        print(f" - {ind} (RSNP: {top_ind_b.loc[ind, 'beats_bench']:.2f})")

if __name__ == "__main__":
    generate_q1_feb_2026_list()
