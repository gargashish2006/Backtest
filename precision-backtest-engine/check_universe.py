import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def check_ongc_universe():
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    
    date = pd.Timestamp("2026-02-05")
    metrics = dh.get_daily_metrics(date)
    metrics = metrics.sort_values('mc', ascending=False)
    
    ongc_isin = "INE213A01029"
    pw_isin = "INE372C01037"
    
    print(f"--- Universe Check ---")
    if ongc_isin in metrics['isin'].values:
        rank = (metrics['isin'] == ongc_isin).idxmax() + 1 # Error here, it's not ID but index
        # Better:
        rank = list(metrics['isin']).index(ongc_isin) + 1
        mc = metrics[metrics['isin'] == ongc_isin]['mc'].iloc[0]
        print(f"ONGC Rank: {rank}, MC: {mc:,.0f}")
    else:
        print("ONGC not in metrics at all.")
        
    if pw_isin in metrics['isin'].values:
        rank = list(metrics['isin']).index(pw_isin) + 1
        mc = metrics[metrics['isin'] == pw_isin]['mc'].iloc[0]
        print(f"Precision Wires Rank: {rank}, MC: {mc:,.0f}")
    else:
        print("Precision Wires not in metrics at all.")

    top_1000 = metrics.head(1000)
    print(f"ONGC in Top 1000? {ongc_isin in top_1000['isin'].values}")
    print(f"PW in Top 1000? {pw_isin in top_1000['isin'].values}")

if __name__ == "__main__":
    check_ongc_universe()
