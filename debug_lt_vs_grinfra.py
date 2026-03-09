import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def debug_lt_vs_grinfra_v2():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    date = pd.Timestamp("2025-08-14")
    lt_isin = "INE018A01030" # L&T
    gr_isin = "INE201P01022" # GR Infra
    
    print(f"--- Meta Inspection ---")
    for isin, name in [(lt_isin, "L&T"), (gr_isin, "GR Infra")]:
        ind = dh.isin_to_industry.get(isin, "N/A")
        grp = dh.isin_to_group.get(isin, "N/A")
        print(f"{name} ({isin}): Industry={ind}, Group={grp}")

    # 2. Shareholding
    sh_trend = dh.get_shareholder_trend(date)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    
    grp_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count'])
    valid_groups = grp_stats[grp_stats['count'] >= 5].sort_values('mean', ascending=False)
    num_to_pick = int(len(valid_groups) * 0.50)
    top_groups = valid_groups.head(num_to_pick).index.tolist()
    
    print(f"\nConstruction Group Stats: Mean={grp_stats.loc['Construction', 'mean']:.2%}, Count={grp_stats.loc['Construction', 'count']}")
    print(f"Is 'Construction' in Top 50% groups? {'YES' if 'Construction' in top_groups else 'NO'}")

    # 3. Market Cap Ranking
    actual_calc_date = max([d for d in dh.get_all_dates() if d <= (date - pd.Timedelta(days=7))])
    metrics = dh.get_daily_metrics(actual_calc_date).sort_values('mc', ascending=False)
    universe = metrics.head(1000)
    
    print(f"\n--- Universe Rankings ---")
    for isin, name in [(lt_isin, "L&T"), (gr_isin, "GR Infra")]:
        in_uni = isin in universe['isin'].values
        rank = list(universe['isin']).index(isin) + 1 if in_uni else "N/A"
        mc = universe[universe['isin'] == isin]['mc'].iloc[0] if in_uni else 0
        print(f"{name} in Top 1000? {in_uni} (Rank: {rank}, MC: {mc:,.0f})")

if __name__ == "__main__":
    debug_lt_vs_grinfra_v2()
