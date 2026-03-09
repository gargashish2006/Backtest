import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.industry_shareholding import IndustryShareholdingStrategy

def analyze_rebalance():
    # Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # Setup Strategy
    strategy = IndustryShareholdingStrategy(dh)
    
    # Rebalance Date (Feb 15 or latest available)
    all_dates = dh.get_all_dates()
    rebalance_date = max([dt for dt in all_dates if dt <= pd.Timestamp("2026-02-15")])
    
    print(f"\n==========================================")
    print(f"ANALYZING REBALANCE: {rebalance_date.date()}")
    print(f"==========================================\n")
    
    # Run selection
    selection = strategy.calculate_selection(rebalance_date)
    
    # 1. Show Qualifying Industries (Breadth >= 60%)
    sh_trend = dh.get_shareholder_trend(rebalance_date)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    ind_stats = sh_trend.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    ind_stats = ind_stats.rename(columns={'mean': 'consolidation_rate'})
    
    # Filter using same logic as strategy
    qualified = ind_stats[(ind_stats['consolidation_rate'] >= strategy.consolidation_threshold) & 
                          (ind_stats['count'] >= 3)].copy()
    
    # Rank them by RSNP (Win Rate)
    # Reuse strategy's logic for consistency
    calc_date = rebalance_date - pd.Timedelta(days=strategy.lag_days)
    lookback_start = calc_date - pd.Timedelta(days=strategy.lookback_days)
    
    bench_df = dh.top_1000_bench
    p_bench_end = bench_df[bench_df['date'] <= calc_date]['index_value'].iloc[-1]
    p_bench_start = bench_df[bench_df['date'] <= lookback_start]['index_value'].iloc[-1]
    bench_return = (p_bench_end / p_bench_start) - 1
    
    metrics = dh.get_daily_metrics(calc_date)
    top_1000 = metrics.sort_values('mc', ascending=False).head(strategy.universe_size)
    eligible_isins = top_1000['isin'].tolist()
    
    all_dates = dh.get_all_dates()
    actual_end_date = max([d for d in all_dates if d <= calc_date])
    actual_start_date = max([d for d in all_dates if d <= lookback_start])
    
    p_end_map = dh.get_daily_prices(actual_end_date)
    p_start_map = dh.get_daily_prices(actual_start_date)
    
    stock_returns = []
    for isin in eligible_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            stock_returns.append({'isin': isin, 'return': ret})
            
    ret_df = pd.DataFrame(stock_returns)
    ret_df['industry'] = ret_df['isin'].map(dh.isin_to_industry)
    ret_df['is_winner'] = ret_df['return'] > bench_return
    
    rsnp_stats = ret_df.groupby('industry')['is_winner'].agg(['mean', 'count']).reset_index()
    rsnp_stats = rsnp_stats.rename(columns={'mean': 'win_rate'})
    
    ranked_industries = rsnp_stats[rsnp_stats['industry'].isin(qualified['industry'])].copy()
    ranked_industries = ranked_industries.sort_values(['win_rate', 'count'], ascending=False)
    
    print("TOP QUALIFIED INDUSTRIES (BY RSNP/WIN RATE):")
    print(ranked_industries.head(10))
    
    print("\n" + "="*50)
    print("FEB 2026 REBALANCE SELECTION (MAX 15 STOCKS)")
    print("="*50)
    if not selection:
        print("NO STOCKS SELECTED")
    else:
        for isin, weight in selection.items():
            name = dh.isin_to_name.get(isin, "Unknown")
            industry = dh.isin_to_industry.get(isin, "Unknown")
            print(f"{name:<30} | {industry:<25} | {weight*100:>5.1f}%")
    print("="*50)

if __name__ == "__main__":
    analyze_rebalance()
