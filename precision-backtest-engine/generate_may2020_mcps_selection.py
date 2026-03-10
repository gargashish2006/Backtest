"""
MCPS12-4Q Portfolio Snapshot (May 15, 2020)
Generates the historical stock list for the optimized MCPS strategy.
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

# Strategy Parameters (Locked in MCPS12-4Q)
s = MCPSStrategy(dh, num_stocks=12, universe_size=1000)

rebalance_date = pd.Timestamp("2020-05-15")

# Precompute RSI for the target date
s.precompute_rsi([rebalance_date])

# Calculate selection
selection = s.calculate_selection(rebalance_date)

if not selection:
    print("No stocks selected for the given date.")
else:
    results = []
    for isin, weight in selection.items():
        results.append({
            'ISIN': isin,
            'Company': dh.isin_to_name.get(isin, 'Unknown'),
            'Industry': dh.isin_to_industry.get(isin, 'Unknown'),
            'Group': dh.isin_to_group.get(isin, 'Unknown'),
            'Weight': f"{weight*100:.1f}%"
        })
    
    df_result = pd.DataFrame(results)
    
    print("\n" + "=" * 105)
    print(f"MCPS12-4Q HISTORICAL PORTFOLIO Snapshot (Effective: 15-May-2020)")
    print("=" * 105)
    print(df_result.to_string(index=False))
    print("=" * 105)
    print(f"Total Stocks: {len(selection)}")
