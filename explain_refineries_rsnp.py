import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def explain_refineries_rsnp():
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database/price_data.parquet")
    dh = DataHandler(data_path)
    dh.load_data()
    
    industry_name = "Refineries & Marketing"
    isins = [isin for isin, ind in dh.isin_to_industry.items() if ind == industry_name]
    
    date = pd.Timestamp("2026-02-05")
    lag_date = date - pd.Timedelta(days=7)
    lookback_date = lag_date - pd.Timedelta(days=365)
    
    all_dates = dh.get_all_dates()
    actual_end_date = max([d for d in all_dates if d <= lag_date])
    actual_start_date = max([d for d in all_dates if d <= lookback_date])
    
    p_end_map = dh.get_daily_prices(actual_end_date)
    p_start_map = dh.get_daily_prices(actual_start_date)
    
    bench_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks/Benchmark_1000_equalWeight.parquet")
    bench_df = pd.read_parquet(bench_path)
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    p_bench_end = bench_df[bench_df['date'] <= actual_end_date]['index_value'].iloc[-1]
    p_bench_start = bench_df[bench_df['date'] <= actual_start_date]['index_value'].iloc[-1]
    bench_return = (p_bench_end / p_bench_start) - 1
    
    print(f"================================================================================")
    print(f"RSNP ANALYSIS: {industry_name}")
    print(f"Calculation Date: {actual_end_date.date()}")
    print(f"Benchmark (Top 1000) Return: {bench_return*100:.2f}%")
    print(f"================================================================================")
    
    results = []
    for isin in isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        name = dh.isin_to_name.get(isin, isin)
        
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            beats_bench = ret > bench_return
            results.append({
                'Stock Name': name,
                '1-yr Return': f"{ret*100:.2f}%",
                'Beats Bench?': "YES" if beats_bench else "NO"
            })
        else:
            results.append({
                'Stock Name': name,
                '1-yr Return': "N/A",
                'Beats Bench?': "EXCLUDED"
            })
            
    df_results = pd.DataFrame(results)
    valid_results = [r for r in results if r['Beats Bench?'] != "EXCLUDED"]
    num_wins = sum(1 for r in valid_results if r['Beats Bench?'] == "YES")
    rsnp_score = num_wins / len(valid_results) if valid_results else 0
    
    print(df_results.to_string(index=False))
    print(f"================================================================================")
    print(f"FINAL RSNP SCORE: {rsnp_score:.3f} ({num_wins}/{len(valid_results)})")
    print(f"================================================================================")

if __name__ == "__main__":
    explain_refineries_rsnp()
