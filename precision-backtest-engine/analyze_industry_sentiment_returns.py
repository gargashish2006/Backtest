"""
Industry Sentiment vs Forward Returns Analysis (v2 - canonical industries).
For each quarter, compute trailing 3-month post count per industry from ValuePickr,
then measure forward 3-month returns from our industry benchmarks.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

REPO = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
DB_PATH = REPO / "database" / "valuepickr_posts.parquet"
BENCH_DIR = REPO / "benchmarks" / "industries"
OUTPUT_DIR = REPO


def load_industry_timeseries(industries):
    """Load benchmark timeseries for given canonical industry names."""
    ts_map = {}
    for ind in industries:
        dir_name = ind.replace(' ', '_').replace('/', '_')
        ts_path = BENCH_DIR / dir_name / "timeseries.csv"
        if ts_path.exists():
            df = pd.read_csv(ts_path)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            ts_map[ind] = df
    return ts_map


def compute_forward_return(ts_df, start_date, months=3):
    """Compute forward N-month return from start_date."""
    end_date = start_date + pd.DateOffset(months=months)
    mask_start = ts_df['date'] >= start_date
    if mask_start.sum() == 0:
        return None
    start_val = ts_df.loc[mask_start, 'index_value'].iloc[0]

    end_candidates = ts_df[(ts_df['date'] >= end_date - pd.Timedelta(days=14)) &
                           (ts_df['date'] <= end_date + pd.Timedelta(days=14))]
    if len(end_candidates) == 0 or start_val == 0:
        return None
    end_val = end_candidates['index_value'].iloc[-1]
    return (end_val / start_val - 1) * 100


def main():
    print("Loading ValuePickr posts...")
    df_posts = pd.read_parquet(DB_PATH)
    df_posts['created_at'] = pd.to_datetime(df_posts['created_at']).dt.tz_localize(None)
    df_posts = df_posts[df_posts['industry'] != 'Other / Unclassified']
    
    vp_industries = sorted(df_posts['industry'].unique())
    print(f"  {len(df_posts)} classified posts across {len(vp_industries)} industries")

    print("\nLoading industry benchmarks...")
    ts_map = load_industry_timeseries(vp_industries)
    print(f"  {len(ts_map)} industry timeseries loaded")

    eval_dates = pd.date_range('2016-06-30', '2025-09-30', freq='QE')
    print(f"  {len(eval_dates)} quarterly evaluation points")

    results = []
    for eval_date in eval_dates:
        lookback_start = eval_date - pd.DateOffset(months=3)
        for ind in vp_industries:
            if ind not in ts_map:
                continue
            mask = ((df_posts['industry'] == ind) &
                    (df_posts['created_at'] >= lookback_start) &
                    (df_posts['created_at'] <= eval_date))
            post_count = mask.sum()
            fwd_return = compute_forward_return(ts_map[ind], eval_date)
            if fwd_return is not None:
                results.append({
                    'eval_date': eval_date,
                    'industry': ind,
                    'trailing_3m_posts': post_count,
                    'forward_3m_return': fwd_return,
                })

    df_results = pd.DataFrame(results)
    print(f"\n  {len(df_results)} industry-quarter observations")

    # ── Quintile Analysis ─────────────────────────────────────────────
    def assign_quintile(group):
        group = group.copy()
        active = group['trailing_3m_posts'] > 0
        group['quintile'] = 0
        if active.sum() >= 5:
            try:
                group.loc[active, 'quintile'] = pd.qcut(
                    group.loc[active, 'trailing_3m_posts'].rank(method='first'),
                    q=5, labels=[1, 2, 3, 4, 5]
                ).astype(int)
            except Exception:
                ranks = group.loc[active, 'trailing_3m_posts'].rank(pct=True)
                group.loc[active, 'quintile'] = (ranks * 5).clip(1, 5).astype(int)
        elif active.sum() > 0:
            med = group.loc[active, 'trailing_3m_posts'].median()
            group.loc[active, 'quintile'] = (group.loc[active, 'trailing_3m_posts'] > med).astype(int) + 1
        return group

    df_results = df_results.groupby('eval_date', group_keys=False).apply(assign_quintile)

    quintile_summary = df_results[df_results['quintile'] > 0].groupby('quintile').agg(
        avg_fwd_return=('forward_3m_return', 'mean'),
        median_fwd_return=('forward_3m_return', 'median'),
        count=('forward_3m_return', 'count'),
        avg_posts=('trailing_3m_posts', 'mean'),
    ).round(2)

    print("\n" + "=" * 70)
    print("QUINTILE ANALYSIS: Trailing 3M Post Count → Forward 3M Return")
    print("(Q1 = least discussed, Q5 = most discussed)")
    print("=" * 70)
    print(quintile_summary.to_string())

    no_disc = df_results[df_results['quintile'] == 0]
    if len(no_disc) > 0:
        print(f"\nNo Discussion (0 posts): avg fwd return = {no_disc['forward_3m_return'].mean():.2f}%, "
              f"median = {no_disc['forward_3m_return'].median():.2f}%, n={len(no_disc)}")

    # ── Top vs Bottom over time ───────────────────────────────────────
    top_vs_bottom = df_results[df_results['quintile'].isin([1, 5])].copy()
    top_vs_bottom['group'] = top_vs_bottom['quintile'].map({1: 'Bottom (Q1)', 5: 'Top (Q5)'})
    pivot = top_vs_bottom.pivot_table(
        values='forward_3m_return', index='eval_date', columns='group', aggfunc='mean')

    # ── Plots ─────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(14, 12))

    ax1 = axes[0]
    q_data = quintile_summary[['avg_fwd_return', 'median_fwd_return']]
    q_data.plot(kind='bar', ax=ax1, color=['steelblue', 'coral'])
    ax1.set_title('Avg Forward 3M Return by Discussion Quintile (84 Canonical Industries)',
                  fontsize=14, fontweight='bold')
    ax1.set_xlabel('Discussion Quintile (Q1=Least → Q5=Most Discussed)')
    ax1.set_ylabel('Forward 3-Month Return (%)')
    ax1.axhline(y=0, color='grey', linestyle='--', alpha=0.5)
    ax1.legend(['Mean', 'Median'])
    ax1.grid(axis='y', alpha=0.3)

    ax2 = axes[1]
    if 'Bottom (Q1)' in pivot.columns and 'Top (Q5)' in pivot.columns:
        pivot.plot(ax=ax2, linewidth=2)
        spread = pivot['Top (Q5)'] - pivot['Bottom (Q1)']
        spread.plot(ax=ax2, linewidth=2, linestyle='--', label='Spread (Q5 - Q1)', color='green')
    ax2.set_title('Top vs Bottom Discussed: Forward 3M Returns Over Time',
                  fontsize=14, fontweight='bold')
    ax2.set_ylabel('Forward 3-Month Return (%)')
    ax2.axhline(y=0, color='grey', linestyle='--', alpha=0.5)
    ax2.legend()
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    out_path = OUTPUT_DIR / "industry_sentiment_vs_returns_v2.png"
    plt.savefig(out_path, dpi=150)
    print(f"\nPlot saved to: {out_path}")

    # ── Per-industry table ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("TOP 30 INDUSTRIES by avg discussion volume")
    print("=" * 70)
    per_ind = df_results.groupby('industry').agg(
        avg_posts=('trailing_3m_posts', 'mean'),
        avg_fwd_return=('forward_3m_return', 'mean'),
        observations=('forward_3m_return', 'count'),
    ).sort_values('avg_posts', ascending=False)

    print(f"\n{'Industry':<50} {'Avg Posts/Q':>10} {'Avg Fwd 3M':>12} {'Obs':>5}")
    print("-" * 80)
    for ind, row in per_ind.head(30).iterrows():
        print(f"{ind[:48]:<50} {row['avg_posts']:>10.1f} {row['avg_fwd_return']:>11.2f}% {row['observations']:>5.0f}")

    corr = per_ind[['avg_posts', 'avg_fwd_return']].corr().iloc[0, 1]
    print(f"\nCorrelation (avg posts vs avg fwd return): {corr:.3f}")

    # ── Oct 2025 snapshot with forward returns ────────────────────────
    print("\n" + "=" * 70)
    print("OCT 2025 SNAPSHOT: Trailing 3M posts → Nov-Jan Forward Return")
    print("=" * 70)
    oct_data = df_results[df_results['eval_date'] == '2025-09-30'].sort_values('trailing_3m_posts', ascending=False)
    print(f"\n{'Rank':<5} {'Industry':<50} {'Posts':>6} {'Fwd 3M':>10}")
    print("-" * 75)
    for i, (_, row) in enumerate(oct_data.iterrows(), 1):
        if row['trailing_3m_posts'] > 0:
            print(f"{i:<5} {row['industry'][:48]:<50} {row['trailing_3m_posts']:>6.0f} {row['forward_3m_return']:>9.1f}%")

    df_results.to_csv(OUTPUT_DIR / "industry_sentiment_vs_returns_v2.csv", index=False)
    print(f"\nFull results saved to: industry_sentiment_vs_returns_v2.csv")


if __name__ == "__main__":
    main()
