import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from strategies.cs15_strategy import CS15Strategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

rebalance_date = pd.Timestamp("2026-02-15")
all_dates = dh.get_all_dates()
actual_date = max([d for d in all_dates if d <= rebalance_date])
print(f"Actual rebalance date used: {actual_date.date()}")

# ─── Helper to extract qualified industries ───────────────────────────────────
def get_qualified_industries(strat, signal_date, label):
    actual_signal = max([d for d in all_dates if d <= signal_date])
    actual_lookback = max([d for d in all_dates if d <= (actual_signal - pd.DateOffset(years=1))])
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"  Signal date : {actual_signal.date()}")
    print(f"  Lookback    : {actual_lookback.date()}")
    print(f"{'='*60}")

    # Step 1: Shareholder trend
    sh_trend = dh.get_shareholder_trend(actual_signal, lookback_quarters=4)
    if sh_trend.empty:
        print("  ❌ No shareholder data available.")
        return

    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)

    # Step 2: Group filter (top 50%)
    group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
    group_stats = group_stats.sort_values('decreased', ascending=False)
    top_n = max(1, int(len(group_stats) * 0.50))
    top_groups = group_stats.head(top_n)['group'].tolist()
    print(f"\n  Top {top_n}/{len(group_stats)} Industry Groups (by breadth):")
    for _, row in group_stats.head(top_n).iterrows():
        print(f"    {row['group']:<40} {row['decreased']*100:.1f}%")

    # Step 3: Industry breadth filter (>= 50%)
    ind_sh = sh_trend[sh_trend['group'].isin(top_groups)]
    ind_stats = ind_sh.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
    ind_stats = ind_stats.sort_values('mean', ascending=False)
    qualified = ind_stats[ind_stats['mean'] >= 0.50]
    not_qualified = ind_stats[ind_stats['mean'] < 0.50]

    print(f"\n  ✅ Qualified Industries (breadth >= 50%) — {len(qualified)} industries:")
    for _, row in qualified.iterrows():
        print(f"    {row['industry']:<45} {row['mean']*100:.1f}%  (n={int(row['count'])})")

    print(f"\n  ❌ Rejected Industries (breadth < 50%) — {len(not_qualified)} industries:")
    for _, row in not_qualified.iterrows():
        print(f"    {row['industry']:<45} {row['mean']*100:.1f}%  (n={int(row['count'])})")

    # Step 4: RSNP filter
    b_prices = dh.top_1000_bench
    b_end = b_prices[b_prices['date'] <= actual_signal]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= actual_lookback]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    print(f"\n  Benchmark 1Y Return: {bench_return*100:.2f}%")

    def get_map(d):
        w = [x for x in all_dates if x <= d][-30:]
        return dh.price_df[dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()

    p1 = get_map(actual_signal)
    p0 = get_map(actual_lookback)

    qualified_inds = qualified['industry'].tolist()
    rsnp_results = []
    for ind in qualified_inds:
        isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
        wins, total = 0, 0
        for i in isins:
            c1, c0 = p1.get(i), p0.get(i)
            if c1 and c0 and c0 > 0:
                total += 1
                if (c1/c0 - 1) > bench_return:
                    wins += 1
        if total > 0:
            rsnp_results.append({'industry': ind, 'rsnp': wins/total, 'n': total})

    rsnp_df = pd.DataFrame(rsnp_results).sort_values('rsnp', ascending=False)
    passed_rsnp = rsnp_df[rsnp_df['rsnp'] >= 0.40]
    failed_rsnp = rsnp_df[rsnp_df['rsnp'] < 0.40]

    print(f"\n  ✅ Passed RSNP (>= 40%) — {len(passed_rsnp)} industries:")
    for _, row in passed_rsnp.iterrows():
        print(f"    {row['industry']:<45} RSNP={row['rsnp']*100:.1f}%  (n={int(row['n'])})")

    print(f"\n  ❌ Failed RSNP (< 40%) — {len(failed_rsnp)} industries:")
    for _, row in failed_rsnp.iterrows():
        print(f"    {row['industry']:<45} RSNP={row['rsnp']*100:.1f}%  (n={int(row['n'])})")

# ─── Run for Champion (T+0) ───────────────────────────────────────────────────
get_qualified_industries(None, actual_date, "CHAMPION — Signal Date: T+0 (Feb 15, 2026)")

# ─── Run for CS15 (T-7) ──────────────────────────────────────────────────────
signal_date_cs15 = actual_date - pd.Timedelta(days=7)
get_qualified_industries(None, signal_date_cs15, "CS15 — Signal Date: T-7 (Feb 8, 2026)")
