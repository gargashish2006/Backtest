import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_feb_2026_sh_purity_list():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # Rebalance Date
    date = pd.Timestamp("2026-02-05") # Production date for Feb-2026 signal
    
    # 1. Shareholder Data (8Q lookback as per baseline)
    sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
    if sh_trend.empty:
        print("Error: No shareholding data found.")
        return

    # 2. Enrich with Industry/Group
    stocks_info = []
    for _, row in sh_trend.iterrows():
        isin = row['isin']
        if isin in dh.isin_to_group and isin in dh.isin_to_industry:
            stocks_info.append({
                'isin': isin,
                'name': dh.isin_to_name.get(isin, "Unknown"),
                'group': dh.isin_to_group[isin],
                'industry': dh.isin_to_industry[isin],
                'decreased': row['decreased'],
                'curr_sh': row['curr_sh'],
                'prev_sh': row['prev_sh'],
                'sh_change_pct': ((row['curr_sh'] - row['prev_sh']) / row['prev_sh']) if row['prev_sh'] > 0 else 0
            })
            
    df_info = pd.DataFrame(stocks_info)
    
    # 3. Hierarchical Breadth Calculation
    # Group Breadth
    group_stats = df_info.groupby('group')['decreased'].mean()
    top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35))).index.tolist()
    
    # Industry Breadth (within top groups)
    rel_df = df_info[df_info['group'].isin(top_groups)]
    ind_stats = rel_df.groupby('industry')['decreased'].mean()
    top_industries = ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()
    
    # 4. Filter for Qualified Pool (35/35 + Top 1000)
    qualified_df = rel_df[rel_df['industry'].isin(top_industries)].copy()
    
    # Market Cap (Top 1000)
    univ = dh.get_universe(date, size=1000)
    univ_isins = set(univ['isin'].tolist())
    
    final_pool = qualified_df[qualified_df['isin'].isin(univ_isins)].copy()
    
    # 5. Add Breadth Stats for the columns
    final_pool['group_breadth'] = final_pool['group'].map(group_stats)
    final_pool['industry_breadth'] = final_pool['industry'].map(ind_stats)
    
    # 6. Rank by SH Change % (Ascending = deepest decrease)
    final_pool = final_pool.sort_values('sh_change_pct', ascending=True)
    
    # 7. Final Output Selection
    output_cols = [
        'isin', 'name', 'sh_change_pct', 'industry', 'industry_breadth', 
        'group', 'group_breadth', 'curr_sh', 'prev_sh'
    ]
    final_list = final_pool[output_cols]
    
    # Format Percentages for Excel readability
    final_list['sh_change_pct'] = (final_list['sh_change_pct'] * 100).round(2)
    final_list['industry_breadth'] = (final_list['industry_breadth'] * 100).round(2)
    final_list['group_breadth'] = (final_list['group_breadth'] * 100).round(2)
    
    # Rename for Clarity
    final_list.columns = [
        'ISIN', 'Company Name', 'SH Change %', 'Industry', 'Industry Breadth %',
        'Industry Group', 'Group Breadth %', 'Current SH', 'Previous SH (8Q Ago)'
    ]
    
    # 8. Save to Excel
    output_path = repo_root / "outputs/Feb_2026_SH_Change_Purity_Full_List.xlsx"
    final_list.to_excel(output_path, index=False)
    
    print(f"Total Qualified Stocks: {len(final_list)}")
    print(f"Top 10 Stocks by Decrease %:")
    print(final_list.head(10).to_string(index=False))
    print(f"\nFinal list saved to: {output_path}")

if __name__ == "__main__":
    generate_feb_2026_sh_purity_list()
