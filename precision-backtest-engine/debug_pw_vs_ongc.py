import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def debug_selection_clash():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    date = pd.Timestamp("2026-02-15")
    
    # 1. Check ONGC vs Precision Wires Metadata
    ongc_isin = "INE213A01029" # ONGC
    pw_isin = "INE372C01037"   # Precision Wires
    
    print(f"--- Meta Inspection ---")
    for isin, name in [(pw_isin, "Precision Wires"), (ongc_isin, "ONGC")]:
        ind = dh.isin_to_industry.get(isin, "N/A")
        grp = dh.isin_to_group.get(isin, "N/A")
        print(f"{name} ({isin}): Industry={ind}, Group={grp}")

    # 2. Check Shareholder Decrease Stats
    sh_trend = dh.get_shareholder_trend(date)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    # Group mean decrease
    group_stats = sh_trend.groupby('group')['decreased'].mean().sort_values(ascending=False)
    # Industry mean decrease
    ind_stats = sh_trend.groupby('industry')['decreased'].mean().sort_values(ascending=False)
    
    pw_ind = dh.isin_to_industry.get(pw_isin)
    pw_grp = dh.isin_to_group.get(pw_isin)
    ongc_ind = dh.isin_to_industry.get(ongc_isin)
    ongc_grp = dh.isin_to_group.get(ongc_isin)
    
    print(f"\n--- Shareholder Stats ---")
    print(f"Precision Wires Industry ({pw_ind}): {ind_stats.get(pw_ind, 'N/A'):.2%}")
    print(f"Precision Wires Group ({pw_grp}): {group_stats.get(pw_grp, 'N/A'):.2%}")
    
    if ongc_ind in ind_stats:
        print(f"ONGC Industry ({ongc_ind}): {ind_stats.get(ongc_ind, 'N/A'):.2%}")
        print(f"ONGC Group ({ongc_grp}): {group_stats.get(ongc_grp, 'N/A'):.2%}")
    else:
        print(f"ONGC or its Industry ({ongc_ind}) not found in Shareholder patterns for this quarter.")

    # 3. Check Group Ranking (Relative Top 50%)
    valid_groups = group_stats[sh_trend.groupby('group')['decreased'].count() >= 5]
    threshold_rank = int(len(valid_groups) * 0.50)
    top_groups = valid_groups.head(threshold_rank).index.tolist()
    
    print(f"\n--- Group Filter (Relative Top 50%) ---")
    print(f"PW Group ({pw_grp}) in Top Groups? {'YES' if pw_grp in top_groups else 'NO'}")
    if ongc_grp:
        print(f"ONGC Group ({ongc_grp}) in Top Groups? {'YES' if ongc_grp in top_groups else 'NO'}")

    # 5. RSNP Check
    actual_lookback_start = max([d for d in dh.get_all_dates() if d <= (date - pd.Timedelta(days=365+7))])
    actual_calc_date = max([d for d in dh.get_all_dates() if d <= (date - pd.Timedelta(days=7))])
    
    b_end = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_calc_date]['index_value'].iloc[-1]
    b_start = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_lookback_start]['index_value'].iloc[-1]
    bench_return = (b_end / b_start) - 1
    
    print(f"\n--- RSNP Inspection ---")
    print(f"Bench Return: {bench_return:.2%}")
    
    for ind in [pw_ind, ongc_ind]:
        ind_isins = [isin for isin, name in dh.isin_to_industry.items() if name == ind]
        wins = 0
        eligible = 0
        for isin in ind_isins:
            prices = dh.price_df[dh.price_df['isin'] == isin]
            p0_df = prices[prices['date'] <= actual_lookback_start]
            p1_df = prices[prices['date'] <= actual_calc_date]
            if not p0_df.empty and not p1_df.empty:
                p0 = p0_df.iloc[-1]['close']
                p1 = p1_df.iloc[-1]['close']
                ret = (p1/p0) - 1
                eligible += 1
                if ret > bench_return:
                    wins += 1
        rsnp = wins/eligible if eligible > 0 else 0
        print(f"Industry: {ind}, RSNP: {rsnp:.2f} ({wins}/{eligible})")

if __name__ == "__main__":
    debug_selection_clash()
