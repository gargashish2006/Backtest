import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def calculate_all_industry_rsnp():
    # Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # Dates
    # Current date is Feb 11, 2026. Max price data is Feb 5, 2026.
    end_date = pd.Timestamp("2026-02-05")
    start_date = end_date - pd.Timedelta(days=365)
    
    # Actual dates in data
    all_dates = dh.get_all_dates()
    actual_end = max([d for d in all_dates if d <= end_date])
    actual_start = max([d for d in all_dates if d <= start_date])
    
    # Get Benchmark Return
    # Using Benchmark_1000_equalWeight.parquet
    bench_df = pd.read_parquet(bench_dir / "Benchmark_1000_equalWeight.parquet")
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    b_end = bench_df[bench_df['date'] <= actual_end]['index_value'].iloc[-1]
    b_start = bench_df[bench_df['date'] <= actual_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    print(f"Period: {actual_start.date()} to {actual_end.date()}")
    print(f"Benchmark (Top 1000) Return: {bench_return*100:.2f}%\n")

    # Get Robust Price Maps (5-day window for missing data)
    def get_robust_price_map(target_date, lookback_window=5):
        window_dates = [d for d in all_dates if d <= target_date][-lookback_window:]
        robust_map = {}
        for d in window_dates:
            daily = dh.get_daily_prices(d)
            for isin, p in daily.items():
                robust_map[isin] = p
        return robust_map

    p_end_map = get_robust_price_map(actual_end)
    p_start_map = get_robust_price_map(actual_start)
    
    # Calculate for ALL ISINs in the mapping
    industry_data = []
    for isin, industry in dh.isin_to_industry.items():
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        
        is_winner = False
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            if ret > bench_return:
                is_winner = True
        
        industry_data.append({'industry': industry, 'is_winner': is_winner})
        
    df = pd.DataFrame(industry_data)
    
    # Group by industry
    rsnp_report = df.groupby('industry')['is_winner'].agg(['mean', 'count']).reset_index()
    rsnp_report = rsnp_report.rename(columns={'mean': 'rsnp_score', 'count': 'total_stocks'})
    
    # Sort by RSNP Score
    rsnp_report = rsnp_report.sort_values(['rsnp_score', 'total_stocks'], ascending=False)
    
    # Output to CSV for user
    output_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/outputs/all_industries_rsnp.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rsnp_report.to_csv(output_path, index=False)
    
    print("Top 50 Industries by RSNP Score:")
    print("="*80)
    print(rsnp_report.head(50).to_string(index=False))
    print("="*80)
    print(f"\nFull report saved to: {output_path}")

if __name__ == "__main__":
    calculate_all_industry_rsnp()
