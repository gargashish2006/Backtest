"""
Research: Median shareholder change % -> forward returns (cross-sectional)

Signal : Median % change in total_shareholders per industry / industry group
         vs N quarters ago. Ranked cross-sectionally within each quarter.

Return windows (from signal quarter end, top-500 stocks by market cap):
  1Q : quarter end -> +1Q
  6M : quarter end -> +2Q
  1Y : quarter end -> +4Q

All lookbacks (4Q / 8Q / 12Q) restricted to the same signal quarters.
Run separately for industry and industry group.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys, os

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from data.data_handler import DataHandler

QUARTER_END = {'Mar': (3,31), 'Jun': (6,30), 'Sep': (9,30), 'Dec': (12,31)}

def quarter_to_start_date(q_str):
    code, year = q_str.split('-')
    year = int(year)
    starts = {'Mar': (1,1), 'Jun': (4,1), 'Sep': (7,1), 'Dec': (10,1)}
    m, d = starts[code]
    return pd.Timestamp(year=year, month=m, day=d)

def quarter_to_end_date(q_str):
    code, year = q_str.split('-')
    year = int(year)
    m, d = QUARTER_END[code]
    return pd.Timestamp(year=year, month=m, day=d)

def next_quarter(q_str):
    order = ['Mar','Jun','Sep','Dec']
    code, year = q_str.split('-')
    year = int(year)
    idx = order.index(code)
    return f"Mar-{year+1}" if idx == 3 else f"{order[idx+1]}-{year}"

def add_n_quarters(q_str, n):
    q = q_str
    for _ in range(n):
        q = next_quarter(q)
    return q

def rank_quartile(x, qlabels):
    """Assign quartiles by rank within the group (robust to ties/duplicates)."""
    pct = x.rank(pct=True, method='average')
    return pd.cut(pct, bins=[0, 0.25, 0.5, 0.75, 1.0],
                  labels=qlabels, include_lowest=True)

def run_level(dh, sh_df, quarters, all_dates, grouping, isin_map, level_name,
              signal='median_sh_chg'):
    """
    Run the full analysis for one grouping level (industry or industry group).
    signal: 'median_sh_chg'  -> median % change in shareholders
            'decrease_pct'   -> % of stocks with declining shareholders
    Returns dict of {lookback: DataFrame}.
    """
    valid_quarters = [q for q in quarters if q.split('-')[0] in QUARTER_END]

    LOOKBACKS    = [4, 8, 12]
    MAX_LOOKBACK = max(LOOKBACKS)

    common_quarters = [
        q for q in valid_quarters
        if quarters.index(q) - MAX_LOOKBACK >= 0
        and quarter_to_end_date(add_n_quarters(q, 8)) <= pd.Timestamp(all_dates[-1])
    ]

    def get_nearest_price(date):
        valid = [d for d in all_dates if d <= date]
        return dh.get_daily_prices(max(valid)) if valid else {}

    def grp_eq_return(isins, p_from, p_to):
        if not p_from or not p_to:
            return np.nan
        rets = [p_to[i] / p_from[i] - 1
                for i in isins
                if p_from.get(i) and p_to.get(i) and p_from[i] > 0]
        return np.mean(rets) * 100 if len(rets) >= 3 else np.nan

    all_results = {}

    for lb in LOOKBACKS:
        records = []
        for q in common_quarters:
            prev_q = quarters[quarters.index(q) - lb]
            t = [quarter_to_end_date(add_n_quarters(q, n)) for n in range(9)]

            curr = sh_df[sh_df['quarter'] == q][['isin', grouping, 'total_shareholders']].rename(
                columns={'total_shareholders': 'curr_sh'})
            prev = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(
                columns={'total_shareholders': 'prev_sh'})

            merged = curr.merge(prev, on='isin', how='inner')
            merged = merged[(merged['curr_sh'] > 0) & (merged['prev_sh'] > 0)]
            merged['sh_chg_pct'] = (merged['curr_sh'] - merged['prev_sh']) / merged['prev_sh'] * 100
            merged['decreased']  = merged['curr_sh'] < merged['prev_sh']

            grp_stats = merged.groupby(grouping).agg(
                n_stocks=('sh_chg_pct', 'count'),
                median_sh_chg=('sh_chg_pct', 'median'),
                decrease_pct=('decreased', 'mean'),
            ).reset_index()
            grp_stats['decrease_pct'] *= 100
            grp_stats = grp_stats[grp_stats['n_stocks'] >= 3]
            if grp_stats.empty:
                continue

            top500_date  = max(d for d in all_dates if d <= t[0])
            top500_isins = set(dh.get_universe(top500_date, size=500)['isin'].tolist())
            prices = [get_nearest_price(d) for d in t]

            for _, row in grp_stats.iterrows():
                grp   = row[grouping]
                isins = [i for i, n in isin_map.items() if n == grp and i in top500_isins]
                r1q = grp_eq_return(isins, prices[0], prices[1])
                r6m = grp_eq_return(isins, prices[0], prices[2])
                r1y = grp_eq_return(isins, prices[0], prices[4])
                r2y = grp_eq_return(isins, prices[0], prices[8])
                if any(np.isnan(v) for v in [r1q, r6m, r1y, r2y]):
                    continue
                records.append({
                    'signal_quarter': q,
                    grouping:         grp,
                    'n_stocks_sh':    row['n_stocks'],
                    'median_sh_chg':  row['median_sh_chg'],
                    'decrease_pct':   row['decrease_pct'],
                    'ret_1q': r1q, 'ret_6m': r6m, 'ret_1y': r1y, 'ret_2y': r2y,
                })

        all_results[lb] = pd.DataFrame(records)

    # Restrict to shared signal quarters
    shared_qtrs = set(all_results[LOOKBACKS[0]]['signal_quarter'])
    for lb in LOOKBACKS[1:]:
        shared_qtrs &= set(all_results[lb]['signal_quarter'])

    qlabels = ['Q1 (Low)', 'Q2', 'Q3', 'Q4 (High)']
    for lb in LOOKBACKS:
        df = all_results[lb][all_results[lb]['signal_quarter'].isin(shared_qtrs)].copy()
        df['quartile'] = (
            df.groupby('signal_quarter')[signal]
            .transform(lambda x: rank_quartile(x, qlabels))
        )
        all_results[lb] = df

    n_shared = len(shared_qtrs)
    print(f"\n{'='*68}")
    print(f"  {level_name.upper()} — Shared quarters: {n_shared}")
    print(f"{'='*68}")

    ret_cols   = ['ret_1q', 'ret_6m', 'ret_1y', 'ret_2y']
    ret_labels = ['1Q return', '6M return', '1Y return', '2Y return']

    for stat_name, stat_fn in [('MEAN', 'mean'), ('MEDIAN', 'median')]:
        print(f"\n{stat_name}:")
        header = f"  {'LB':<6}{'Quartile':<16}" + \
                 "".join(f"{l:>12}" for l in ret_labels) + f"{'n':>7}"
        print(header)
        print("  " + "-"*72)
        for lb in LOOKBACKS:
            df  = all_results[lb]
            tbl = df.groupby('quartile', observed=True).agg(
                n=('ret_1q', 'count'),
                ret_1q=('ret_1q', stat_fn),
                ret_6m=('ret_6m', stat_fn),
                ret_1y=('ret_1y', stat_fn),
                ret_2y=('ret_2y', stat_fn),
            ).reset_index()
            for _, row in tbl.iterrows():
                print(f"  {lb}Q    {str(row['quartile']):<16}"
                      f"{row['ret_1q']:>11.1f}%"
                      f"{row['ret_6m']:>11.1f}%"
                      f"{row['ret_1y']:>11.1f}%"
                      f"{row['ret_2y']:>11.1f}%"
                      f"{int(row['n']):>7}")
            print()

    print(f"  Pearson r ({signal} vs return):")
    hdr = f"  {'LB':<6}" + "".join(f"{l:>12}" for l in ret_labels)
    print(hdr)
    print("  " + "-"*54)
    for lb in LOOKBACKS:
        df  = all_results[lb]
        row = f"  {lb}Q    "
        for col in ret_cols:
            sub = df[[signal, col]].dropna()
            r   = sub[signal].corr(sub[col])
            row += f"{r:>+11.3f}"
        print(row)

    return all_results


def plot_both(results_ind, results_grp, LOOKBACKS, signal='median_sh_chg'):
    """Plot mean + median for both levels side by side."""
    qlabels   = ['Q1\n(Low)', 'Q2', 'Q3', 'Q4\n(High)']
    ret_cols  = ['ret_1q', 'ret_6m', 'ret_1y', 'ret_2y']
    ret_lbls  = ['1Q', '6M', '1Y', '2Y']
    q_colors  = ['#4575b4','#91bfdb','#fc8d59','#d73027']
    lb_colors = {4:'steelblue', 8:'seagreen', 12:'mediumpurple'}
    levels    = [('Industry', results_ind), ('Industry Group', results_grp)]

    # 2 levels × 3 lookbacks rows, 3 cols (1Q/6M/1Y), each cell has mean bar + median dot
    nrows = len(LOOKBACKS)
    ncols = len(ret_cols)

    for level_name, all_results in levels:
        fig, axes = plt.subplots(nrows, ncols, figsize=(13, 3.5 * nrows),
                                 gridspec_kw={'hspace': 0.50, 'wspace': 0.28})
        for ri, lb in enumerate(LOOKBACKS):
            df    = all_results[lb]
            color = lb_colors[lb]
            mean_tbl = df.groupby('quartile', observed=True)[ret_cols].mean()
            med_tbl  = df.groupby('quartile', observed=True)[ret_cols].median()

            for ci, (col, lbl) in enumerate(zip(ret_cols, ret_lbls)):
                ax    = axes[ri, ci]
                vals  = mean_tbl[col].values
                mvals = med_tbl[col].values

                ax.bar(range(4), vals, color=q_colors, edgecolor='white', width=0.6)
                ax.scatter(range(4), mvals, color='black', zorder=5, s=40,
                           label='Median' if (ri == 0 and ci == 0) else '')
                ax.axhline(0, color='black', linewidth=0.5)

                for xi, (v, mv) in enumerate(zip(vals, mvals)):
                    ax.text(xi, v + 0.3 if v >= 0 else v - 1.5,
                            f'{v:.1f}%', ha='center', va='bottom', fontsize=7)

                sub = df[[signal, col]].dropna()
                r   = sub[signal].corr(sub[col])
                title = f'{lbl}  r={r:+.3f}'
                if ci == 0:
                    title = f'LB={lb}Q | {title}'
                ax.set_title(title, fontsize=8.5, fontweight='bold',
                             color=color if ci == 0 else 'black')
                ax.set_xticks(range(4))
                ax.set_xticklabels(qlabels, fontsize=7)
                ax.set_ylabel('Return (%)', fontsize=8) if ci == 0 else None
                ax.tick_params(axis='y', labelsize=7)
                if ri == 0 and ci == 0:
                    ax.legend(fontsize=7)

        sig_title = 'Median Shareholder Change %' if signal == 'median_sh_chg' else '% Stocks with Shareholder Decrease'
        fig.suptitle(
            f'{sig_title} -> {level_name} Returns\n'
            'Cross-sectional quartiles within each quarter | Top-500 stocks | Full-universe signal\n'
            'Bars = mean, dots = median  |  Low = biggest decline, High = biggest increase',
            fontsize=11, fontweight='bold'
        )
        slug     = level_name.lower().replace(' ', '_')
        sig_slug = signal
        out  = REPO_ROOT / "outputs" / f"sh_{sig_slug}_cross_sectional_{slug}.png"
        fig.savefig(out, dpi=150, bbox_inches='tight')
        print(f"\nPlot saved -> {out}")
        plt.show()


def main():
    dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
    dh.load_data()
    all_dates = dh.get_all_dates()

    sh_df    = dh.shareholding_df.copy()
    quarters = sorted(sh_df['quarter'].unique(), key=quarter_to_start_date)
    print(f"Quarters: {quarters[0]} to {quarters[-1]} ({len(quarters)} total)")

    # Attach both grouping columns
    sh_df['industry'] = sh_df['isin'].map(dh.isin_to_industry)
    sh_df['group']    = sh_df['isin'].map(dh.isin_to_group)
    sh_df = sh_df[sh_df['total_shareholders'] > 0]

    LOOKBACKS = [4, 8, 12]

    for signal in ['median_sh_chg', 'decrease_pct']:
        print(f"\n{'#'*70}")
        print(f"  SIGNAL: {signal}")
        print(f"{'#'*70}")

        results_ind = run_level(
            dh, sh_df[sh_df['industry'].notna()].copy(),
            quarters, all_dates,
            grouping='industry', isin_map=dh.isin_to_industry,
            level_name='Industry', signal=signal
        )

        results_grp = run_level(
            dh, sh_df[sh_df['group'].notna()].copy(),
            quarters, all_dates,
            grouping='group', isin_map=dh.isin_to_group,
            level_name='Industry Group', signal=signal
        )

        plot_both(results_ind, results_grp, LOOKBACKS, signal=signal)

        combined = pd.concat(
            [df.assign(lookback=lb, level='industry') for lb, df in results_ind.items()] +
            [df.assign(lookback=lb, level='group')    for lb, df in results_grp.items()],
            ignore_index=True
        )
        out_csv = REPO_ROOT / "outputs" / f"sh_{signal}_cross_sectional.csv"
        combined.to_csv(out_csv, index=False)
        print(f"Data saved -> outputs/sh_{signal}_cross_sectional.csv")


if __name__ == "__main__":
    main()
