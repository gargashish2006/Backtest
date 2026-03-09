import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def calculate_industry_rsnp_and_sh():
    # Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # Dates for RSNP
    end_date = pd.Timestamp("2026-02-05")
    start_date = end_date - pd.Timedelta(days=365)
    all_dates = dh.get_all_dates()
    actual_end = max([d for d in all_dates if d <= end_date])
    actual_start = max([d for d in all_dates if d <= start_date])
    
    # 1. Benchmark Return
    bench_df = pd.read_parquet(bench_dir / "Benchmark_1000_equalWeight.parquet")
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    b_end = bench_df[bench_df['date'] <= actual_end]['index_value'].iloc[-1]
    b_start = bench_df[bench_df['date'] <= actual_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    # 2. RSNP Calculation (Windowed lookup)
    def get_robust_price_map(target_date, lookback_window=30):
        window_dates = [d for d in all_dates if d <= target_date][-lookback_window:]
        robust_map = {}
        for d in window_dates:
            daily = dh.get_daily_prices(d)
            for isin, p in daily.items():
                robust_map[isin] = p
        return robust_map

    p_end_map = get_robust_price_map(actual_end)
    p_start_map = get_robust_price_map(actual_start)
    
    rsnp_data = []
    for isin, industry in dh.isin_to_industry.items():
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        is_winner = False
        if p1 and p0 and p0 > 0:
            if (p1 / p0) - 1 > bench_return:
                is_winner = True
        rsnp_data.append({'isin': isin, 'industry': industry, 'is_winner': is_winner})
    
    rsnp_df = pd.DataFrame(rsnp_data)
    rsnp_grouped = rsnp_df.groupby('industry').agg(
        rsnp_score=('is_winner', 'mean'),
        total_stocks=('isin', 'count')
    ).reset_index()

    # 3. Shareholding Consolidation (Dec-24 to Dec-25)
    # Rebalance date in Feb 2026 will use Dec-25 vs Dec-24 logic in DataHandler
    sh_trend = dh.get_shareholder_trend(pd.Timestamp("2026-02-05"))
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    sh_grouped = sh_trend.groupby('industry').agg(
        sh_consolidation_pct=('decreased', 'mean'),
        sh_stock_count=('isin', 'count')
    ).reset_index()

    # 4. Merge Reports
    final_report = pd.merge(rsnp_grouped, sh_grouped, on='industry', how='left')
    
    # Final cleanup
    final_report = final_report.sort_values('rsnp_score', ascending=False)
    
    # Save output
    output_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/outputs/industry_rsnp_and_sh.csv")
    final_report.to_csv(output_path, index=False)
    
    print(f"Report Generated for period ending Dec-2025.")
    print(f"Benchmark Return: {bench_return*100:.2f}%\n")
    print("TOP 50 INDUSTRIES BY RSNP SCORE (With SH Consolidation):")
    print("="*100)
    # Format for display
    display_df = final_report.head(50).copy()
    display_df['rsnp_score'] = display_df['rsnp_score'].round(3)
    display_df['sh_consolidation_pct'] = (display_df['sh_consolidation_pct'] * 100).fillna(0).round(1).astype(str) + '%'
    
    print(display_df[['industry', 'total_stocks', 'rsnp_score', 'sh_consolidation_pct', 'sh_stock_count']].to_string(index=False))
    print("="*100)
    print(f"\nFull report saved to: {output_path}")

if __name__ == "__main__":
    calculate_industry_rsnp_and_sh()
