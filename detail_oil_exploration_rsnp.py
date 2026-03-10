import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def detail_oil_exploration_rsnp():
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database/price_data.parquet")
    dh = DataHandler(data_path)
    dh.load_data()
    
    industry_name = "Oil Exploration & Production"
    all_mapped_isins = [isin for isin, ind in dh.isin_to_industry.items() if ind == industry_name]
    
    end_date = pd.Timestamp("2026-02-05")
    start_date = end_date - pd.Timedelta(days=365)
    
    all_dates = dh.get_all_dates()
    actual_end_date = max([d for d in all_dates if d <= end_date])
    actual_start_date = max([d for d in all_dates if d <= start_date])
    
    # Benchmark Return (-2.62% as calculated in previous main report)
    bench_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks/Benchmark_1000_equalWeight.parquet")
    bench_df = pd.read_parquet(bench_path)
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    p_bench_end = bench_df[bench_df['date'] <= actual_end_date]['index_value'].iloc[-1]
    p_bench_start = bench_df[bench_df['date'] <= actual_start_date]['index_value'].iloc[-1]
    bench_return = (p_bench_end / p_bench_start) - 1
    
    # Robust Price Maps (30-day window)
    def get_robust_price_map(target_date, lookback_window=30):
        window_dates = [d for d in all_dates if d <= target_date][-lookback_window:]
        robust_map = {}
        for d in window_dates:
            daily = dh.get_daily_prices(d)
            for isin, p in daily.items():
                robust_map[isin] = p
        return robust_map

    p_end_map = get_robust_price_map(actual_end_date)
    p_start_map = get_robust_price_map(actual_start_date)
    
    print(f"================================================================================")
    print(f"RSNP DETAIL: {industry_name}")
    print(f"Benchmark Return (Top 1000): {bench_return*100:.2f}%")
    print(f"================================================================================")
    
    details = []
    for isin in all_mapped_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        name = dh.isin_to_name.get(isin, isin)
        
        ret = "N/A"
        winner = False
        if p1 and p0 and p0 > 0:
            ret_val = (p1 / p0) - 1
            ret = f"{ret_val*100:.2f}%"
            if ret_val > bench_return:
                winner = True
        
        details.append({
            'Stock Name': name,
            '1-yr Return': ret,
            'Beats Benchmark?': "YES" if winner else "NO"
        })
        
    df_details = pd.DataFrame(details)
    num_wins = sum(1 for d in details if d['Beats Benchmark?'] == "YES")
    total_active = len(all_mapped_isins)
    final_score = num_wins / total_active
    
    print(df_details.to_string(index=False))
    print(f"================================================================================")
    print(f"RSNP Score: {num_wins} Wins / {total_active} Total = {final_score:.4f}")
    print(f"================================================================================")

if __name__ == "__main__":
    detail_oil_exploration_rsnp()
