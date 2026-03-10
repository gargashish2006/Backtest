import pandas as pd
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_momentum.IM_Top1000_Small import IM_Top1000_Small

def export_feb_2025_im_ranking():
    strat = IM_Top1000_Small()
    strat.load_data()
    
    # REBALANCE DATE
    date = pd.Timestamp('2025-02-15')
    rs_date = date - pd.Timedelta(days=7) # 7-day lag
    
    print(f"Ranking Industries for: {date.date()}")
    print(f"Signal Date (Lagged): {rs_date.date()}")
    
    # Need to reproduce the selection logic part that calculates RSNP for all industries
    # 1. Bench Ret
    end_bench = strat.universe_bench[strat.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
    start_date_bench = rs_date - pd.Timedelta(days=strat.RS_LOOKBACK_DAYS)
    start_bench = strat.universe_bench[strat.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
    bench_ret = (end_bench / start_bench) - 1
    
    print(f"Benchmark Return (365d): {bench_ret:.2%}")
    
    # 2. RSNP for all industries
    all_industries = strat.industry_df['industry'].unique()
    rsnp_results = []
    for ind in all_industries:
        rsnp = strat.calculate_rsnp(ind, rs_date, strat.RS_LOOKBACK_DAYS, bench_ret)
        avg_ret = strat.get_industry_ret(ind, rs_date, strat.RS_LOOKBACK_DAYS)
        count = len(strat.industry_df[strat.industry_df['industry'] == ind])
        rsnp_results.append({
            'Industry': ind,
            'RSNP Score': rsnp,
            'Avg Return': f"{avg_ret:.2%}" if avg_ret is not None else "N/A",
            'Stock Count': count
        })
    
    df_report = pd.DataFrame(rsnp_results).sort_values(['RSNP Score', 'Avg Return'], ascending=False)
    
    # Get top 10
    top_10 = df_report.head(10)
    
    print("\n" + "="*60)
    print("TOP 10 INDUSTRIES - INDUSTRY MOMENTUM (FEB 2025)")
    print("="*60)
    print(top_10.to_string(index=False))
    print("="*60)
    
    # Save to outputs
    out = Path(project_root) / 'strategies/industry_momentum/outputs' / 'feb_2025_industry_ranking_im.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    df_report.to_csv(out, index=False)
    print(f"Full report saved to: {out}")

if __name__ == "__main__":
    export_feb_2025_im_ranking()
