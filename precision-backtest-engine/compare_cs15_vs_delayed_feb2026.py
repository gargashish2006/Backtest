"""
Compare CS15 vs CS15_delayed industry RSNP lists for the Feb 2026 rebalance.
"""
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).parent

from data.data_handler import DataHandler
from strategies.cs15_strategy import CS15Strategy
from strategies.cs15_delayed_strategy import CS15DelayedStrategy

dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
dh.load_data()
dh.load_benchmarks(REPO_ROOT / "benchmarks")

all_dates = dh.get_all_dates()
rebalance_date = max([d for d in all_dates if d <= pd.Timestamp("2026-02-15")])
print(f"Rebalance date: {rebalance_date.date()}")

# --- shared signal date ---
signal_date = rebalance_date - pd.Timedelta(days=7)
actual_signal_date = max([d for d in all_dates if d <= signal_date])
print(f"Signal date:    {actual_signal_date.date()}")

# --- CS15_delayed: RSNP window ---
def curr_quarter_end(date):
    y, m = date.year, date.month
    if 2 <= m < 5:  return pd.Timestamp(year=y-1, month=12, day=31)
    if 5 <= m < 8:  return pd.Timestamp(year=y,   month=3,  day=31)
    if 8 <= m < 11: return pd.Timestamp(year=y,   month=6,  day=30)
    base = y if m >= 11 else y - 1
    return pd.Timestamp(year=base, month=9, day=30)

q_end = curr_quarter_end(rebalance_date)
rsnp_end_delayed = max([d for d in all_dates if d <= q_end])
rsnp_start_delayed = max([d for d in all_dates if d <= rsnp_end_delayed - pd.DateOffset(years=1)])

actual_lookback_start_cs15 = max([d for d in all_dates if d <= actual_signal_date - pd.DateOffset(years=1)])

print(f"\nRSNP window - CS15:         {actual_lookback_start_cs15.date()} to {actual_signal_date.date()}")
print(f"RSNP window - CS15_delayed: {rsnp_start_delayed.date()} to {rsnp_end_delayed.date()}")

# --- helper: compute RSNP per industry ---
def compute_industry_rsnp(b_prices, rsnp_end, rsnp_start, qualified_industries):
    b_end = b_prices[b_prices['date'] <= rsnp_end]['index_value'].iloc[-1]
    b_start = b_prices[b_prices['date'] <= rsnp_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1

    def get_map(d):
        w = [x for x in all_dates if x <= d][-30:]
        return dh.price_df[dh.price_df['date'].isin(w)]\
            .sort_values('date').groupby('isin')['close'].last().to_dict()

    p1 = get_map(rsnp_end)
    p0 = get_map(rsnp_start)

    rows = []
    for ind in qualified_industries:
        isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
        wins, total = 0, 0
        for i in isins:
            c1, c0 = p1.get(i), p0.get(i)
            if c1 and c0 and c0 > 0:
                total += 1
                if (c1/c0 - 1) > bench_return: wins += 1
        if total > 0:
            rows.append({'industry': ind, 'rsnp': wins/total, 'stocks': total})
    return pd.DataFrame(rows).sort_values('rsnp', ascending=False), bench_return

# --- shared shareholder filter (same for both) ---
RSNP_THRESHOLD = 0.40
sh_trend = dh.get_shareholder_trend(actual_signal_date, lookback_quarters=4)
sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
top_groups = group_stats.sort_values('decreased', ascending=False)\
    .head(int(len(group_stats) * 0.50))['group'].tolist()
ind_sh = sh_trend[sh_trend['group'].isin(top_groups)]
ind_stats = ind_sh.groupby('industry')['decreased'].mean().reset_index()
qualified_industries = ind_stats[ind_stats['decreased'] >= 0.50]['industry'].tolist()
print(f"\nQualified industries (shareholder filter): {len(qualified_industries)}")

b_prices = dh.indices_bench.get('NIFTY 500')

# --- CS15 RSNP ---
rsnp_cs15, bench_cs15 = compute_industry_rsnp(
    b_prices, actual_signal_date, actual_lookback_start_cs15, qualified_industries)
rsnp_cs15['passed'] = rsnp_cs15['rsnp'] >= RSNP_THRESHOLD

# --- CS15_delayed RSNP ---
rsnp_delayed, bench_delayed = compute_industry_rsnp(
    b_prices, rsnp_end_delayed, rsnp_start_delayed, qualified_industries)
rsnp_delayed['passed'] = rsnp_delayed['rsnp'] >= RSNP_THRESHOLD

print(f"\nBenchmark return — CS15:         {bench_cs15*100:.2f}%")
print(f"Benchmark return — CS15_delayed: {bench_delayed*100:.2f}%")

# --- Merge & compare ---
merged = pd.merge(
    rsnp_cs15[['industry','rsnp','stocks','passed']].rename(
        columns={'rsnp':'rsnp_cs15','passed':'pass_cs15'}),
    rsnp_delayed[['industry','rsnp','passed']].rename(
        columns={'rsnp':'rsnp_delayed','passed':'pass_delayed'}),
    on='industry', how='outer'
).sort_values('rsnp_cs15', ascending=False)

merged['status'] = merged.apply(lambda r:
    'BOTH' if r['pass_cs15'] and r['pass_delayed'] else
    'CS15 only' if r['pass_cs15'] and not r['pass_delayed'] else
    'DELAYED only' if not r['pass_cs15'] and r['pass_delayed'] else
    'neither', axis=1)

print(f"\n{'Industry':<45} {'RSNP_CS15':>10} {'RSNP_DLY':>10} {'Stocks':>7} {'Status'}")
print("-" * 90)
for _, row in merged.iterrows():
    cs15_val = f"{row['rsnp_cs15']*100:.1f}%" if pd.notna(row['rsnp_cs15']) else "  —"
    dly_val  = f"{row['rsnp_delayed']*100:.1f}%" if pd.notna(row['rsnp_delayed']) else "  —"
    stocks   = int(row['stocks']) if pd.notna(row.get('stocks')) else "—"
    print(f"{row['industry']:<45} {cs15_val:>10} {dly_val:>10} {str(stocks):>7}   {row['status']}")

print(f"\nSummary:")
print(f"  Passed in both:         {(merged['status']=='BOTH').sum()}")
print(f"  CS15 only (dropped):    {(merged['status']=='CS15 only').sum()}")
print(f"  DELAYED only (new):     {(merged['status']=='DELAYED only').sum()}")
print(f"  Passed in neither:      {(merged['status']=='neither').sum()}")
