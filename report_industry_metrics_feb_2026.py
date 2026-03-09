import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def report_industry_metrics():
    # Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # Date: February 2026 rebalance (look at data around Feb 5-15)
    all_dates = dh.get_all_dates()
    rebalance_date = max([dt for dt in all_dates if dt <= pd.Timestamp("2026-02-15")])
    lag_days = 7
    calc_date = rebalance_date - pd.Timedelta(days=lag_days)
    lookback_days = 365
    lookback_start = calc_date - pd.Timedelta(days=lookback_days)
    
    # 1. Shareholding Consolidation %
    sh_trend = dh.get_shareholder_trend(rebalance_date)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    ind_stats = sh_trend.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    ind_stats = ind_stats.rename(columns={'mean': 'consolidation_pct', 'count': 'stock_count'})
    
    # Filter for >= 60% and count >= 3
    qualified = ind_stats[(ind_stats['consolidation_pct'] >= 0.60) & (ind_stats['stock_count'] >= 3)].copy()
    
    # 2. Momentum Score (Industry Benchmark 12m Return)
    # 3. RSNP Score (Win Rate vs Top 1000 Benchmark)
    
    # Get Benchmark Return
    bench_df = dh.top_1000_bench
    p_bench_end = bench_df[bench_df['date'] <= calc_date]['index_value'].iloc[-1]
    p_bench_start = bench_df[bench_df['date'] <= lookback_start]['index_value'].iloc[-1]
    bench_return = (p_bench_end / p_bench_start) - 1
    
    # Stock returns for RSNP (Proper breadth: all stocks in industry)
    metrics = dh.get_daily_metrics(calc_date)
    all_isins = metrics['isin'].tolist()
    
    actual_end_date = max([d for d in all_dates if d <= calc_date])
    actual_start_date = max([d for d in all_dates if d <= lookback_start])
    p_end_map = dh.get_daily_prices(actual_end_date)
    p_start_map = dh.get_daily_prices(actual_start_date)
    
    stock_returns = []
    for isin in all_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            stock_returns.append({'isin': isin, 'return': ret})
            
    ret_df = pd.DataFrame(stock_returns)
    ret_df['industry'] = ret_df['isin'].map(dh.isin_to_industry)
    ret_df['is_winner'] = ret_df['return'] > bench_return
    rsnp_stats = ret_df.groupby('industry')['is_winner'].mean().reset_index().rename(columns={'is_winner': 'rsnp_score'})
    
    # Merge everything
    final_report = pd.merge(qualified, rsnp_stats, on='industry', how='left')
    
    momentum_scores = []
    for ind in final_report['industry']:
        p_end = dh.get_industry_benchmark_price(ind, calc_date)
        p_start = dh.get_industry_benchmark_price(ind, lookback_start)
        if p_start > 0:
            momentum_scores.append((p_end / p_start) - 1)
        else:
            momentum_scores.append(0.0)
            
    final_report['momentum_score'] = momentum_scores
    
    # Formatting
    final_report['consolidation_pct'] = (final_report['consolidation_pct'] * 100).round(1).astype(str) + '%'
    final_report['rsnp_score'] = final_report['rsnp_score'].round(3)
    final_report['momentum_score'] = (final_report['momentum_score'] * 100).round(2).astype(str) + '%'
    
    final_report = final_report.sort_values('momentum_score', ascending=False)
    
    print("\n" + "="*80)
    print(f"INDUSTRY METRICS FOR FEB 2026 REBALANCE (Date: {rebalance_date.date()})")
    print("="*80)
    print(final_report[['industry', 'stock_count', 'consolidation_pct', 'rsnp_score', 'momentum_score']].to_string(index=False))
    print("="*80)

if __name__ == "__main__":
    report_industry_metrics()
