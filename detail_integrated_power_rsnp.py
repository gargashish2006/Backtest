import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def detail_integrated_power_rsnp():
    # Setup
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database/price_data.parquet")
    dh = DataHandler(data_path)
    dh.load_data()
    
    industry_name = "Integrated Power Utilities"
    all_mapped_isins = [isin for isin, ind in dh.isin_to_industry.items() if ind == industry_name]
    
    # Range: 1 year ending Feb 5, 2026
    actual_end_date = pd.Timestamp("2026-02-05")
    lookback_start = actual_end_date - pd.Timedelta(days=365)
    
    all_dates = dh.get_all_dates()
    actual_start_date = max([d for d in all_dates if d <= lookback_start])
    
    # Benchmark Return (-2.62%)
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
    print(f"Period: {actual_start_date.date()} to {actual_end_date.date()}")
    print(f"Benchmark Return (Top 1000): {bench_return*100:.2f}%")
    print(f"================================================================================")
    
    details = []
    for isin in all_mapped_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        name = dh.isin_to_name.get(isin, isin)
        
        ret_str = "N/A"
        winner = False
        if p1 and p0 and p0 > 0:
            ret_val = (p1 / p0) - 1
            ret_str = f"{ret_val*100:.2f}%"
            if ret_val > bench_return:
                winner = True
        
        details.append({
            'Stock Name': name,
            '1-yr Return': ret_str,
            'Beats Benchmark?': "YES" if winner else "NO"
        })
        
    df_details = pd.DataFrame(details)
    num_wins = sum(1 for d in details if d['Beats Benchmark?'] == "YES")
    total_constituents = len(all_mapped_isins)
    rsnp_score = num_wins / total_constituents
    
    print(df_details.to_string(index=False))
    print(f"================================================================================")
    print(f"FINAL RSNP SCORE: {num_wins} Wins / {total_constituents} Total = {rsnp_score:.3f}")
    print(f"================================================================================")

if __name__ == "__main__":
    detail_integrated_power_rsnp()
