import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def run_extraction():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    print("Loading DataHandler...")
    dh.load_data()
    
    dates_to_check = [pd.Timestamp("2025-02-15"), pd.Timestamp("2026-02-01")]
    eval_dates = []
    all_dates = dh.get_all_dates()
    for td in dates_to_check:
        avail = [d for d in all_dates if d >= td]
        if avail:
            eval_dates.append(avail[0])
        else:
            eval_dates.append(all_dates[-1])
            
    eval_dates = list(dict.fromkeys(eval_dates))
    
    all_rows = []
    
    for date in eval_dates:
        print(f"Processing for {date.date()}...")
        sh_trend = dh.get_shareholder_trend(date, lookback_quarters=12)
        if sh_trend.empty: continue
        
        # Calculate individual metric: sh_change
        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in dh.isin_to_group and isin in dh.isin_to_industry:
                sh_change = (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                stocks_info.append({
                    'isin': isin,
                    'group': dh.isin_to_group[isin],
                    'industry': dh.isin_to_industry[isin],
                    'decreased': row['decreased'],
                    'sh_change': sh_change
                })
        
        if not stocks_info: continue
        df = pd.DataFrame(stocks_info)
        
        # Calculate Group metrics
        group_breadth = df.groupby('group')['decreased'].mean()
        group_median = df.groupby('group')['sh_change'].median()
        
        # Calculate Industry metrics
        ind_breadth = df.groupby('industry')['decreased'].mean()
        ind_median = df.groupby('industry')['sh_change'].median()
        
        # Map industries to groups
        ind_to_group = {row['industry']: row['group'] for _, row in df.iterrows()}
        
        for ind, group in ind_to_group.items():
            all_rows.append({
                'Rebalance Date': date.date(),
                'Industry Group': group,
                'Industry': ind,
                'Group Breadth (%)': group_breadth.get(group, 0) * 100,
                'Industry Breadth (%)': ind_breadth.get(ind, 0) * 100,
                'Group Median SH Decrease (%)': group_median.get(group, 0) * 100,
                'Industry Median SH Decrease (%)': ind_median.get(ind, 0) * 100
            })
            
    out_df = pd.DataFrame(all_rows)
    
    # Sort for readability: Date, then Group, then Industry
    out_df = out_df.sort_values(['Rebalance Date', 'Industry Group', 'Industry'])
    
    out_path = repo_root / "outputs/slt15_industry_rebalance_metrics.csv"
    out_df.to_csv(out_path, index=False)
    print(f"Extraction complete! Saved {len(out_df)} rows to {out_path}")
    
if __name__ == "__main__":
    run_extraction()
