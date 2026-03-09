import pandas as pd
import sys
from datetime import datetime
from pathlib import Path
from data.data_handler import DataHandler

def generate_full_slt15_industries(end_str, lookback_quarters=12):
    print(f"\nLoading DataHandler for {end_str} ({lookback_quarters}Q Lookback)...")
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    calc_date = pd.to_datetime(end_str)
    
    # Calculate start date based on lookback quarters (approx 91 days per quarter)
    days_back = int(lookback_quarters * 91.25)
    start_date = calc_date - pd.Timedelta(days=days_back)
    
    date_mask = (dh.price_df['date'] >= start_date) & (dh.price_df['date'] <= calc_date)
    df_window = dh.price_df[date_mask].copy()
    
    valid_dates = sorted(df_window['date'].unique())
    start_q = valid_dates[0]
    end_q = valid_dates[-1]

    print(f"Calculating {lookback_quarters}-Quarter Breadth: {start_q.date()} to {end_q.date()}")

    # We need to compute shareholder change using dh.shareholding_df
    sh_df = dh.get_shareholder_trend(calc_date, lookback_quarters=lookback_quarters)
    if sh_df.empty:
        print("No shareholding data available for this date.")
        return
        
    df_end = df_window[df_window['date'] == end_q].copy()

    # Base Universe: Top 1000
    df_end = df_end.sort_values(by='mc', ascending=False)
    df_end = df_end.head(1000)

    # Merge with shareholder trend
    df_sh = pd.merge(df_end, sh_df, on='isin', how='inner')
    
    # Map industries
    df_sh['Industry'] = df_sh['isin'].map(dh.isin_to_industry)
    df_sh['Industry Group'] = df_sh['isin'].map(dh.isin_to_group)

    repo_root = Path(__file__).parent
    
    # 2. Group Breadth
    group_stats = df_sh.groupby('Industry Group')['decreased'].mean()
    top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35)))
    top_groups_list = top_groups.index.tolist()
    
    print(f"Top 35% Groups: {len(top_groups_list)} out of {len(group_stats)}")
    
    # 3. Industry Breadth (within Top Groups)
    df_qualified = df_sh[df_sh['Industry Group'].isin(top_groups_list)]
    ind_stats = df_qualified.groupby('Industry')['decreased'].mean()
    top_industries = ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35)))
    top_industries_list = top_industries.index.tolist()
    
    print(f"Top 35% Industries (within Top 35% Groups): {len(top_industries_list)} out of {len(ind_stats)}")
    
    # Create final dataframe
    results = []
    for ind, ind_score in top_industries.items():
        # find the group for this industry
        grp = df_sh[df_sh['Industry'] == ind]['Industry Group'].iloc[0]
        grp_score = group_stats[grp]
        
        results.append({
            'Industry': ind,
            'Industry Group': grp,
            'Industry Breadth (12Q % Stocks Decreased)': round(ind_score * 100, 2),
            'Group Breadth (12Q % Stocks Decreased)': round(grp_score * 100, 2)
        })
        
    df_results = pd.DataFrame(results)
    
    date_label = calc_date.strftime('%b%Y')
    output_path = repo_root / f"outputs/SLT15_12Q_Filtered_Industries_{date_label}.xlsx"
    df_results.to_excel(output_path, index=False)
    print(f"Successfully saved {len(df_results)} qualified industries to: {output_path}")

if __name__ == "__main__":
    generate_full_slt15_industries('2025-02-01', lookback_quarters=12)
    generate_full_slt15_industries('2026-02-01', lookback_quarters=12)
