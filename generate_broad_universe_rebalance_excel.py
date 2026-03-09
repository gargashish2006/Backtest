import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_rebalance(dh, date):
    # 1. Shareholder Breadth (8Q) on TOTAL universe
    sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
    if sh_trend.empty: return pd.DataFrame()
    
    # Universal stocks info
    stocks_info = []
    for isin in sh_trend['isin'].tolist():
        if isin in dh.isin_to_group and isin in dh.isin_to_industry:
            stocks_info.append({
                'isin': isin,
                'group': dh.isin_to_group[isin],
                'industry': dh.isin_to_industry[isin],
                'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0]
            })
    
    if not stocks_info: return pd.DataFrame()
    df_info = pd.DataFrame(stocks_info)
    
    # 2. Group Breadth
    group_stats = df_info.groupby('group')['decreased'].mean().rename('group_breadth')
    top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35))).index.tolist()
    
    df_info = df_info.merge(group_stats, on='group')
    
    # 3. Industry Breadth (filtered by group)
    rel_df = df_info[df_info['group'].isin(top_groups)].copy()
    ind_stats = rel_df.groupby('industry')['decreased'].mean().rename('industry_breadth')
    top_industries = ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()
    
    rel_df = rel_df.merge(ind_stats, on='industry')
    
    # Final Selection (Top 1000)
    univ = dh.get_universe(date, size=1000)
    univ_isins = set(univ['isin'].tolist())
    
    selected = rel_df[rel_df['industry'].isin(top_industries) & rel_df['isin'].isin(univ_isins)].copy()
    
    # Add stock names
    identifiers = pd.read_csv(Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database/master_identifiers.csv"))
    isin_to_name = identifiers.set_index('isin')['company_name'].to_dict()
    selected['stock_name'] = selected['isin'].map(isin_to_name)
    
    # Organize columns
    cols = ['isin', 'stock_name', 'group', 'group_breadth', 'industry', 'industry_breadth']
    return selected[cols].sort_values(['group_breadth', 'industry_breadth'], ascending=False)

def run_export():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    dates = [pd.Timestamp("2025-11-18"), pd.Timestamp("2026-02-05")]
    output_path = repo_root / "outputs/Broad_Universe_Rebalance_Nov25_Feb26.xlsx"
    
    with pd.ExcelWriter(output_path) as writer:
        for d in dates:
            print(f"Generating for {d.date()}...")
            df = generate_rebalance(dh, d)
            if not df.empty:
                df.to_excel(writer, sheet_name=str(d.date()), index=False)
                print(f"  Exported {len(df)} stocks.")
            else:
                print(f"  No data for {d.date()}")

if __name__ == "__main__":
    run_export()
