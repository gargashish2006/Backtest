import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_filter_report():
    # 1. Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # Reference Date: Feb 5, 2026
    date = pd.Timestamp("2026-02-05")
    lookback_start = date - pd.Timedelta(days=365)
    
    all_dates = dh.get_all_dates()
    actual_calc_date = max([d for d in all_dates if d <= date])
    actual_lookback_date = max([d for d in all_dates if d <= lookback_start])

    # 2. Benchmark Return (Top 1000)
    bench_df = pd.read_parquet(bench_dir / "Benchmark_1000_equalWeight.parquet")
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    b_end = bench_df[bench_df['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = bench_df[bench_df['date'] <= actual_lookback_date]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1

    # 3. Shareholder Consolidation (Dec-24 vs Dec-25)
    sh_trend = dh.get_shareholder_trend(date)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    sh_stats = sh_trend.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    sh_stats = sh_stats.rename(columns={'mean': 'consolidation_rate', 'count': 'sh_count'})

    # 4. RSNP Scores (Robust Breadth)
    def get_robust_price_map(target_date, lookback_window=30):
        window_dates = [d for d in all_dates if d <= target_date][-lookback_window:]
        robust_map = {}
        for d in window_dates:
            daily = dh.get_daily_prices(d)
            for isin, p in daily.items():
                robust_map[isin] = p
        return robust_map

    p_end_map = get_robust_price_map(actual_calc_date)
    p_start_map = get_robust_price_map(actual_lookback_date)
    
    rsnp_data = []
    for isin, ind in dh.isin_to_industry.items():
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        
        # Only count stocks that have price data for BOTH start and end
        if p1 and p0 and p0 > 0:
            is_winner = ((p1 / p0) - 1 > bench_return)
            rsnp_data.append({'industry': ind, 'is_winner': is_winner})
    
    rsnp_df = pd.DataFrame(rsnp_data)
    rsnp_stats = rsnp_df.groupby('industry')['is_winner'].agg(['mean', 'count']).reset_index()
    rsnp_stats = rsnp_stats.rename(columns={'mean': 'rsnp_score', 'count': 'total_stocks_active'})

    # 5. Industry Momentum (Benchmark Return)
    momentum_data = []
    for industry in dh.isin_to_industry.values():
        if industry not in [m['industry'] for m in momentum_data]:
            p_end = dh.get_industry_benchmark_price(industry, actual_calc_date)
            p_start = dh.get_industry_benchmark_price(industry, actual_lookback_date)
            if p_start > 0:
                ret = (p_end / p_start) - 1
                momentum_data.append({'industry': industry, 'industry_momentum': ret})
    
    mom_df = pd.DataFrame(momentum_data)

    # 6. Final Merge
    report = pd.merge(sh_stats, rsnp_stats, on='industry', how='outer')
    report = pd.merge(report, mom_df, on='industry', how='left')

    # Status Column: Qualified if Consolidation >= 60% and count >= 3
    report['qualified'] = (report['consolidation_rate'] >= 0.60) & (report['sh_count'] >= 3)
    
    # Sorting: Qualified first, then by RSNP
    report = report.sort_values(['qualified', 'rsnp_score', 'industry_momentum'], ascending=[False, False, False])

    # Save
    report.to_csv("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/outputs/rebalance_filter_table_feb_2026.csv", index=False)
    
    print(f"====================================================================================================")
    print(f"CONTRARIAN STRATEGY FILTER TABLE (Feb 5, 2026)")
    print(f"Benchmark (-2.62%) | Threshold: SH Consol >= 60%")
    print(f"====================================================================================================")
    
    display = report.head(40).copy()
    display['consolidation_rate'] = (display['consolidation_rate'] * 100).round(1).astype(str) + "%"
    display['rsnp_score'] = display['rsnp_score'].round(3)
    display['industry_momentum'] = (display['industry_momentum'] * 100).round(1).astype(str) + "%"
    
    cols = ['industry', 'sh_count', 'consolidation_rate', 'rsnp_score', 'industry_momentum', 'qualified']
    print(display[cols].to_string(index=False))
    print(f"====================================================================================================")
    print(f"Full table saved to outputs/rebalance_filter_table_feb_2026.csv")

if __name__ == "__main__":
    generate_filter_report()
