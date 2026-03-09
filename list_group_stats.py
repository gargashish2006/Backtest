import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def list_all_group_stats():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    
    date = pd.Timestamp("2026-02-15")
    sh_trend = dh.get_shareholder_trend(date)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    
    group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
    group_stats = group_stats[group_stats['count'] >= 5]
    group_stats = group_stats.sort_values('mean', ascending=False)
    
    num_to_pick = int(len(group_stats) * 0.50)
    top_groups = group_stats.head(num_to_pick)
    
    print(f"Total Valid Groups: {len(group_stats)}")
    print(f"Top 50% Count: {num_to_pick}")
    print("\n--- Top Groups ---")
    print(top_groups)
    
    print("\n--- Bottom Groups ---")
    print(group_stats.tail(len(group_stats) - num_to_pick))
    
    pw_grp = "Industrial Products"
    ongc_grp = "Oil"
    
    print(f"\nPW Group ({pw_grp}) Rank: {list(group_stats['group']).index(pw_grp) + 1}")
    try:
        print(f"ONGC Group ({ongc_grp}) Rank: {list(group_stats['group']).index(ongc_grp) + 1}")
    except:
        print(f"ONGC Group ({ongc_grp}) not found or too small.")

if __name__ == "__main__":
    list_all_group_stats()
