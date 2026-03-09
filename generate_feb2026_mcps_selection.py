"""
MCPS12-4Q Portfolio Rebalance (Feb 15, 2026)
Generates the stock list for the optimized MCPS strategy.
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

# Strategy Parameters (Locked in MCPS12-4Q)
# num_stocks=12, group_top_pct=0.50, group_lookback=4, mcps_lookback=4
s = MCPSStrategy(dh)

rebalance_date = pd.Timestamp("2026-02-15")
all_dates = dh.get_all_dates()

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
            'Symbol': isin, # Placeholder if symbol map not explicit
            'Industry': dh.isin_to_industry.get(isin, 'Unknown'),
            'Group': dh.isin_to_group.get(isin, 'Unknown'),
            'Weight': f"{weight*100:.1f}%"
        })
    
    df_result = pd.DataFrame(results)
    
    print("\n" + "=" * 100)
    print(f"MCPS12-4Q PORTFOLIO REBALANCE (Effective: 15-Feb-2026)")
    print("=" * 100)
    print(df_result.to_string(index=False))
    print("=" * 100)
    print(f"Total Stocks: {len(selection)}")
