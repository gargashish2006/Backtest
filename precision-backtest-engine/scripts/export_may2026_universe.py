"""
Export top-1000 universe at May 2026 rebalance signal date with all CS15 metrics.
"""
import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

def main():
    from data.data_handler import DataHandler

    dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(REPO_ROOT / "benchmarks")

    all_dates = dh.get_all_dates()

    # May 2026 rebalance date and signal date (1-week lag)
    rebal_date = pd.Timestamp("2026-05-15")
    actual_rebal = max(d for d in all_dates if d <= rebal_date)
    signal_date = rebal_date - pd.Timedelta(days=7)
    actual_signal = max(d for d in all_dates if d <= signal_date)
    lookback_start = max(d for d in all_dates if d <= (actual_signal - pd.DateOffset(years=1)))

    print(f"Rebalance date : {actual_rebal.date()}")
    print(f"Signal date    : {actual_signal.date()}")
    print(f"Lookback start : {lookback_start.date()}")

    # 1. Top 1000 universe at signal date
    universe = dh.get_universe(actual_signal, size=1000)
    print(f"Top 1000 stocks: {len(universe)}")

    df = universe[['isin', 'close', 'mc']].copy()
    df = df.rename(columns={'close': 'price', 'mc': 'market_cap'})
    df['company_name'] = df['isin'].map(dh.isin_to_name)
    df['industry'] = df['isin'].map(dh.isin_to_industry)
    df['industry_group'] = df['isin'].map(dh.isin_to_group)

    # 2. Shareholder trend (current quarter vs 4 quarters ago)
    sh_trend = dh.get_shareholder_trend(actual_signal, lookback_quarters=4)
    print(f"Shareholder trend: {len(sh_trend)} stocks with data")

    # Stock-level: did shareholders decrease?
    sh_stock = sh_trend[['isin', 'curr_sh', 'prev_sh', 'decreased']].copy()
    sh_stock['sh_change_pct'] = ((sh_stock['curr_sh'] - sh_stock['prev_sh']) / sh_stock['prev_sh'] * 100)
    sh_stock = sh_stock.rename(columns={'decreased': 'sh_decreased'})

    df = df.merge(sh_stock[['isin', 'curr_sh', 'prev_sh', 'sh_decreased', 'sh_change_pct']], on='isin', how='left')

    # 3. Industry group & industry decrease percentages
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)

    group_decrease = sh_trend.groupby('group')['decreased'].mean().reset_index()
    group_decrease.columns = ['industry_group', 'group_decrease_pct']
    group_decrease['group_decrease_pct'] *= 100

    industry_decrease = sh_trend.groupby('industry')['decreased'].mean().reset_index()
    industry_decrease.columns = ['industry', 'industry_decrease_pct']
    industry_decrease['industry_decrease_pct'] *= 100

    df = df.merge(group_decrease, on='industry_group', how='left')
    df = df.merge(industry_decrease, on='industry', how='left')

    # 4. RSNP computation for both benchmarks
    def get_price_map(d):
        w = [x for x in all_dates if x <= d][-30:]
        return dh.price_df[dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()

    p1 = get_price_map(actual_signal)
    p0 = get_price_map(lookback_start)

    def compute_benchmark_return(bench_df):
        b_end = bench_df[bench_df['date'] <= actual_signal]['index_value'].iloc[-1]
        b_start = bench_df[bench_df['date'] <= lookback_start]['index_value'].iloc[-1]
        return (b_end / b_start) - 1

    bench_ret_top1000 = compute_benchmark_return(dh.top_1000_bench)
    bench_ret_nifty500 = compute_benchmark_return(dh.nifty_500_bench)
    print(f"Benchmark returns (1Y): top_1000={bench_ret_top1000:.4f}, nifty_500={bench_ret_nifty500:.4f}")

    # Per-industry RSNP
    industries = df['industry'].dropna().unique()
    rsnp_top1000 = {}
    rsnp_nifty500 = {}

    for ind in industries:
        ind_isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
        wins_t, wins_n, total = 0, 0, 0
        for i in ind_isins:
            c1, c0 = p1.get(i), p0.get(i)
            if c1 and c0 and c0 > 0:
                total += 1
                stock_ret = c1 / c0 - 1
                if stock_ret > bench_ret_top1000:
                    wins_t += 1
                if stock_ret > bench_ret_nifty500:
                    wins_n += 1
        if total > 0:
            rsnp_top1000[ind] = wins_t / total
            rsnp_nifty500[ind] = wins_n / total

    df['rsnp_top_1000'] = df['industry'].map(rsnp_top1000)
    df['rsnp_nifty_500'] = df['industry'].map(rsnp_nifty500)

    # 5. Order columns nicely
    df = df.sort_values('market_cap', ascending=False).reset_index(drop=True)
    df.index += 1
    df.index.name = 'rank'

    cols = [
        'isin', 'company_name', 'price', 'market_cap',
        'industry', 'industry_group',
        'group_decrease_pct', 'industry_decrease_pct',
        'sh_decreased', 'sh_change_pct', 'curr_sh', 'prev_sh',
        'rsnp_top_1000', 'rsnp_nifty_500',
    ]
    df = df[cols]

    out_path = REPO_ROOT / "outputs" / "may2026_rebalance_universe.xlsx"
    df.to_excel(out_path)
    print(f"\nSaved {len(df)} stocks -> {out_path}")

    # Quick summary
    print(f"\nIndustries with RSNP >= 0.40 (top_1000): {sum(1 for v in rsnp_top1000.values() if v >= 0.40)}")
    print(f"Industries with RSNP >= 0.40 (nifty_500): {sum(1 for v in rsnp_nifty500.values() if v >= 0.40)}")


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, str(REPO_ROOT))
    os.chdir(REPO_ROOT)
    main()
