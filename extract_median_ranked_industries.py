import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from strategies.slt15_industry_median_rank_strategy import SLT15IndustryMedianRankStrategy

def run():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    print("Loading DataHandler...")
    dh.load_data()
    
    dates = [pd.Timestamp("2025-02-15"), pd.Timestamp("2026-02-01")]
    eval_dates = []
    all_dates = dh.get_all_dates()
    for td in dates:
        avail = [d for d in all_dates if d >= td]
        if avail:
            eval_dates.append(avail[0])
        else:
            eval_dates.append(all_dates[-1])
            
    eval_dates = list(dict.fromkeys(eval_dates))
    
    strat = SLT15IndustryMedianRankStrategy(dh, lookback_quarters=12, num_industries=10, max_per_industry=3)
    
    for date in eval_dates:
        print(f"\n{'='*70}")
        print(f"--- Top 10 Industries by Median SH Decrease for {date.date()} ---")
        print(f"{'='*70}")
        
        top_industries_breadth = strat.get_qualified_industries(date)
        if not top_industries_breadth:
            print("No industries qualified.")
            continue
            
        sh_trend = dh.get_shareholder_trend(date, lookback_quarters=12)
        univ = dh.get_universe(date, size=1000)
        
        if univ.empty or sh_trend.empty: continue
        univ_isins = set(univ['isin'].tolist())
        
        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in univ_isins and isin in dh.isin_to_industry:
                ind = dh.isin_to_industry[isin]
                if ind in top_industries_breadth:
                    stocks_info.append({
                        'isin': isin,
                        'industry': ind,
                        'sh_change_pct': (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                    })
        
        if not stocks_info: continue
        qualified_df = pd.DataFrame(stocks_info)
        # Most negative retail shareholder change first (highest accumulation)
        ind_median = qualified_df.groupby('industry')['sh_change_pct'].median()
        sorted_industries = ind_median.sort_values(ascending=True) 
        
        top_10 = sorted_industries.head(10)
        
        df_out = pd.DataFrame({
            "Industry": top_10.index,
            "Median 12Q SH Decrease": (top_10 * 100).round(2).astype(str).values + '%'
        })
        df_out.index = np.arange(1, len(df_out) + 1)
        print(df_out.to_string())

if __name__ == "__main__":
    run()
