import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def get_q1_selection_for_date(dh, date_str, isin_to_symbol, all_dates):
    date = pd.Timestamp(date_str)
    # Find nearest previous price date
    prices_date = max([d for d in all_dates if d <= date])
    
    # 1. Shareholder Breadth (8Q)
    sh_trend = dh.get_shareholder_trend(prices_date, lookback_quarters=8)
    if sh_trend.empty: return pd.DataFrame(), []
    
    # 2. Universe (Top 1000)
    univ = dh.get_universe(prices_date, size=1000)
    univ_isins = set(univ['isin'].tolist())
    
    # 3. RSNP (1Q = 90d lookback)
    q_ago_date = max([d for d in all_dates if d <= prices_date - pd.Timedelta(days=90)])
    prices = dh.get_daily_prices(prices_date)
    prev_p = dh.get_daily_prices(q_ago_date)
    
    common = set(prices.keys()) & set(prev_p.keys()) & univ_isins
    rets = {isin: (prices[isin]/prev_p[isin]) - 1 for isin in common}
    bench_median = pd.Series(list(rets.values())).median()
    
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
    
    # Selection logic (Top 35/35)
    group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
    top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
    
    rel_df = df_info[df_info['group'].isin(top_groups)]
    ind_stats = rel_df.groupby('industry').agg({'decreased': 'mean', 'beats_bench': 'mean'}).sort_values('decreased', ascending=False)
    top_ind_b = ind_stats.head(int(len(ind_stats) * 0.35))
    
    # Q1 Filter (Bottom 25% RSNP)
    sorted_rsnp = top_ind_b.sort_values('beats_bench')
    q1_inds = sorted_rsnp.head(int(len(sorted_rsnp) * 0.25)).index.tolist()
    
    selection = []
    for ind in q1_inds:
        istks = rel_df[rel_df['industry'] == ind].sort_values('mc', ascending=False)
        top3 = istks.head(3)
        for _, row in top3.iterrows():
            selection.append({
                'Date': str(prices_date.date()),
                'Industry': ind,
                'Symbol': row['symbol'],
                'Name': row['name'],
                'Industry Breadth': top_ind_b.loc[ind, 'decreased'],
                'Industry RSNP': top_ind_b.loc[ind, 'beats_bench']
            })
            
    return pd.DataFrame(selection), q1_inds

def run_historical_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    all_dates = dh.get_all_dates()
    
    master_path = repo_root / "database/master_identifiers.csv"
    isin_to_symbol = dict(zip(pd.read_csv(master_path)['isin'], pd.read_csv(master_path)['nse_symbol'])) if master_path.exists() else {}
    
    dates = ["2025-08-14", "2025-11-14"]
    all_selections = []
    
    for d in dates:
        print(f"\nProcessing {d}...")
        df, q1_inds = get_q1_selection_for_date(dh, d, isin_to_symbol, all_dates)
        if not df.empty:
            all_selections.append(df)
            print(f"Industries for {d}: {', '.join(q1_inds)}")
            
    if all_selections:
        final_df = pd.concat(all_selections)
        output_path = repo_root / "outputs/Historical_Q1_Selections_2025.xlsx"
        final_df.to_excel(output_path, index=False)
        print(f"\nSaved to: {output_path}")
        
if __name__ == "__main__":
    run_historical_study()
