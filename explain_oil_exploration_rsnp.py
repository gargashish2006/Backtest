import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def explain_rsnp_oil_exploration():
    # Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Rebalance Date
    all_dates = dh.get_all_dates()
    rebalance_date = max([dt for dt in all_dates if dt <= pd.Timestamp("2026-02-15")])
    lag_days = 7
    calc_date = rebalance_date - pd.Timedelta(days=lag_days)
    lookback_start = calc_date - pd.Timedelta(days=365)
    
    # 1. Get Benchmark Return (Top 1000)
    bench_df = pd.read_parquet(dh.price_path.parent.parent / "benchmarks" / "Benchmark_1000_equalWeight.parquet")
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    p_bench_end = bench_df[bench_df['date'] <= calc_date]['index_value'].iloc[-1]
    p_bench_start = bench_df[bench_df['date'] <= lookback_start]['index_value'].iloc[-1]
    bench_return = (p_bench_end / p_bench_start) - 1
    
    # 2. Get 1-yr returns for all stocks in "Oil Exploration & Production"
    industry_name = "Oil Exploration & Production"
    oil_isins = [isin for isin, ind in dh.isin_to_industry.items() if ind == industry_name]
    
    actual_end_date = max([d for d in all_dates if d <= calc_date])
    actual_start_date = max([d for d in all_dates if d <= lookback_start])
    
    p_end_map = dh.get_daily_prices(actual_end_date)
    p_start_map = dh.get_daily_prices(actual_start_date)
    
    results = []
    for isin in oil_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        name = dh.isin_to_name.get(isin, isin)
        
        # Check if in Top 1000 (M-Cap check)
        metrics = dh.get_daily_metrics(actual_end_date)
        stock_metric = metrics[metrics['isin'] == isin]
        mcap = stock_metric['mc'].iloc[0] if not stock_metric.empty else 0
        
        # Get shareholder decrease status
        sh_trend = dh.get_shareholder_trend(rebalance_date)
        sh_data = sh_trend[sh_trend['isin'] == isin]
        sh_decreased = sh_data['decreased'].iloc[0] if not sh_data.empty else "N/A"
        
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            beats_bench = ret > bench_return
            results.append({
                'Stock Name': name,
                '1-yr Return': f"{ret*100:.2f}%",
                'Beats Bench?': "YES" if beats_bench else "NO",
                'M-Cap (Cr)': round(mcap/1e7, 0),
                'SH Decrease?': sh_decreased
            })
            
    print(f"\n================================================================================")
    print(f"RSNP ANALYSIS: {industry_name}")
    print(f"Benchmark (Top 1000 1-yr Return): {bench_return*100:.2f}%")
    print(f"================================================================================")
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))
    
    # Calculate RSNP Score (Win Rate of eligible stocks)
    # To be eligible for RSNP, stock MUST have mcap and data
    num_wins = sum(1 for r in results if r['Beats Bench?'] == "YES")
    rsnp_score = num_wins / len(results) if results else 0
    print(f"\nFINAL RSNP SCORE: {rsnp_score:.3f}")
    print(f"================================================================================")

if __name__ == "__main__":
    explain_rsnp_oil_exploration()
