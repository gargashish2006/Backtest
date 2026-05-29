"""Export all industries ranked at Feb 2026 rebalance with SH decrease, RSNP, forward returns."""
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler

REPO = Path(__file__).parent


def main():
    dh = DataHandler(REPO / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(REPO / "benchmarks")
    all_dates = dh.get_all_dates()

    # Feb 2026 rebalance date (15th or nearest before)
    rebalance_date = pd.Timestamp("2026-02-15")
    actual_rebal = max(d for d in all_dates if d <= rebalance_date)

    # 1-week signal lag
    signal_date = rebalance_date - pd.Timedelta(days=7)
    actual_signal = max(d for d in all_dates if d <= signal_date)
    lookback_1y = max(d for d in all_dates if d <= (actual_signal - pd.DateOffset(years=1)))

    # Forward return end: ~3 months later (May 2026)
    fwd_end = pd.Timestamp("2026-05-15")
    actual_fwd_end = max(d for d in all_dates if d <= fwd_end)

    print(f"Rebalance date:  {actual_rebal.date()}")
    print(f"Signal date:     {actual_signal.date()}")
    print(f"Forward end:     {actual_fwd_end.date()}")

    # --- 1. Shareholder decrease by industry (4Q lookback) ---
    sh_4q = dh.get_shareholder_trend(actual_signal, lookback_quarters=4)
    sh_4q['industry'] = sh_4q['isin'].map(dh.isin_to_industry)
    sh_4q['group'] = sh_4q['isin'].map(dh.isin_to_group)

    ind_dec_4q = (sh_4q.groupby('industry')['decreased'].mean() * 100).rename('ind_sh_decrease_4q')
    ind_n_4q = sh_4q.groupby('industry')['decreased'].count().rename('ind_n_stocks')

    # Industry group decrease
    grp_dec_4q = (sh_4q.groupby('group')['decreased'].mean() * 100).rename('grp_sh_decrease_4q')

    # Map each industry to its group
    ind_to_grp = sh_4q.dropna(subset=['industry', 'group']).drop_duplicates('industry').set_index('industry')['group']

    # --- 2. RSNP per industry (vs Nifty 500, 1Y) ---
    b_prices = dh.nifty_500_bench
    b_end_qs = b_prices[b_prices['date'] <= actual_signal]
    b_start_qs = b_prices[b_prices['date'] <= lookback_1y]
    bench_return = (b_end_qs['index_value'].iloc[-1] / b_start_qs['index_value'].iloc[-1]) - 1

    def get_price_map(d):
        w = [x for x in all_dates if x <= d][-30:]
        return (dh.price_df[dh.price_df['date'].isin(w)]
                .sort_values('date').groupby('isin')['close'].last().to_dict())

    p1 = get_price_map(actual_signal)
    p0 = get_price_map(lookback_1y)

    all_industries = set(dh.isin_to_industry.values())
    rsnp_data = []
    for ind in all_industries:
        isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
        wins, total = 0, 0
        for i in isins:
            c1, c0 = p1.get(i), p0.get(i)
            if c1 and c0 and c0 > 0:
                total += 1
                if (c1 / c0 - 1) > bench_return:
                    wins += 1
        if total > 0:
            rsnp_data.append({'industry': ind, 'rsnp': wins / total, 'rsnp_total_stocks': total})
    rsnp_df = pd.DataFrame(rsnp_data).set_index('industry')

    # --- 3. Forward 3-month returns per industry (full, top-1000, top-500) ---
    prices_start = dh.get_daily_prices(actual_rebal)
    prices_end = dh.get_daily_prices(actual_fwd_end)

    top1000 = dh.get_universe(actual_rebal, size=1000)
    top1000_isins = set(top1000['isin'].tolist())

    universes = {
        'full': None,
        'top1000': top1000_isins,
    }

    fwd_dfs = {}
    for univ_name, univ_isins in universes.items():
        fwd_ret_data = []
        for ind in all_industries:
            if univ_isins is not None:
                isins = [i for i, n in dh.isin_to_industry.items() if n == ind and i in univ_isins]
            else:
                isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
            rets = []
            for i in isins:
                s = prices_start.get(i)
                e = prices_end.get(i)
                if s and e and s > 0:
                    rets.append((e / s - 1) * 100)
            if rets:
                fwd_ret_data.append({
                    'industry': ind,
                    f'fwd_3m_ret_{univ_name}': np.mean(rets),
                    f'fwd_3m_n_{univ_name}': len(rets),
                })
        fwd_dfs[univ_name] = pd.DataFrame(fwd_ret_data).set_index('industry')

    # --- Combine everything ---
    result = pd.DataFrame(index=sorted(all_industries))
    result.index.name = 'industry'
    result['industry_group'] = result.index.map(ind_to_grp)
    result['ind_sh_decrease_4q_pct'] = result.index.map(ind_dec_4q)
    result['grp_sh_decrease_4q_pct'] = result['industry_group'].map(grp_dec_4q)
    result['ind_n_stocks'] = result.index.map(ind_n_4q)
    result['rsnp'] = result.index.map(rsnp_df['rsnp'])
    result['rsnp_total_stocks'] = result.index.map(rsnp_df['rsnp_total_stocks'])
    for univ_name in universes:
        fwd = fwd_dfs[univ_name]
        result[f'fwd_3m_ret_{univ_name}'] = result.index.map(fwd[f'fwd_3m_ret_{univ_name}'])
        result[f'fwd_3m_n_{univ_name}'] = result.index.map(fwd[f'fwd_3m_n_{univ_name}'])

    # Sort by RSNP descending
    result = result.sort_values('rsnp', ascending=False)

    # Round
    for col in ['ind_sh_decrease_4q_pct', 'grp_sh_decrease_4q_pct', 'rsnp',
                'fwd_3m_ret_full', 'fwd_3m_ret_top1000']:
        result[col] = result[col].round(2)

    out = REPO / "outputs" / "industry_rankings_feb2026_v2.xlsx"
    result.to_excel(out)
    print(f"\nExported {len(result)} industries to {out}")
    print(f"\nTop 20 by RSNP:")
    print(result.head(20).to_string())


if __name__ == "__main__":
    main()
