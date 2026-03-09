import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_slt15_feb_2026():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # Official Rebalance Date for Feb-2026
    date = pd.Timestamp("2026-02-05")
    
    # 1. Shareholder Data (8Q lookback)
    sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
    if sh_trend.empty:
        print("Error: No data.")
        return

    # 2. Enrich and Filter
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
                'sh_change_pct': ((row['curr_sh'] - row['prev_sh']) / row['prev_sh']) if row['prev_sh'] > 0 else 0
            })
    df_info = pd.DataFrame(stocks_info)
    
    # Breadth Logic (35/35)
    group_stats = df_info.groupby('group')['decreased'].mean()
    top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35))).index.tolist()
    
    rel_df = df_info[df_info['group'].isin(top_groups)]
    ind_stats = rel_df.groupby('industry')['decreased'].mean()
    top_industries_breadth = ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()
    
    qualified_df = rel_df[rel_df['industry'].isin(top_industries_breadth)].copy()
    
    # Top 1000 Market Cap
    univ = dh.get_universe(date, size=1000)
    univ_isins = set(univ['isin'].tolist())
    final_pool = qualified_df[qualified_df['isin'].isin(univ_isins)].copy()
    
    # 3. SLT15 Selection Logic
    # Rank by SH-Change % (Max decrease first)
    sorted_pool = final_pool.sort_values('sh_change_pct', ascending=True)
    
    selected_industries = []
    industry_to_isins = {}
    
    for _, row in sorted_pool.iterrows():
        ind = row['industry']
        isin = row['isin']
        
        if ind not in selected_industries:
            if len(selected_industries) < 5:
                selected_industries.append(ind)
                industry_to_isins[ind] = [isin]
        else:
            if len(industry_to_isins[ind]) < 3:
                industry_to_isins[ind].append(isin)
    
    # 4. Compile Final List
    final_stocks = []
    num_inds = len(selected_industries)
    if num_inds == 0:
        print("No stocks found.")
        return
        
    ind_weight = 1.0 / num_inds
    
    for ind in selected_industries:
        isins = industry_to_isins[ind]
        stock_weight = ind_weight / len(isins)
        for isin in isins:
            row = sorted_pool[sorted_pool['isin'] == isin].iloc[0]
            final_stocks.append({
                'isin': isin,
                'Company Name': row['name'],
                'Industry': ind,
                'SH Change %': round(row['sh_change_pct'] * 100, 2),
                'Weight %': round(stock_weight * 100, 2)
            })
            
    result_df = pd.DataFrame(final_stocks)
    
    # 5. Export
    output_path = repo_root / "outputs/SLT15_Feb2026_Rebalance.xlsx"
    result_df.to_excel(output_path, index=False)
    
    print("SLT15 February 2026 Final Selection:")
    print(result_df.to_string(index=False))
    print(f"\nSaved to: {output_path}")

if __name__ == "__main__":
    generate_slt15_feb_2026()
