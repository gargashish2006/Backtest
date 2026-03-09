
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from research_quadrants import QuadrantStrategy

def get_failure_industries():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_trading_dates = dh.get_all_dates()
    
    # Target Rebalance Date: Feb 2026
    d = pd.Timestamp(year=2026, month=2, day=15)
    valid = [dt for dt in all_trading_dates if dt <= d]
    if not valid:
        print("No valid trading date found for Feb 2026")
        return
    rebalance_date = max(valid)
    print(f"Diagnostics for Rebalance Date: {rebalance_date}")

    # Failure Strategy: Bottom Group, Low Breadth, Low RSNP
    strategy = QuadrantStrategy(
        dh, group_mode='bottom', industry_mode='low', rsnp_mode='low',
        num_stocks=15, max_per_industry=3, rsnp_threshold=0.40
    )
    
    # We need to manually trigger the internal logic or use calculate_selection
    # Note: calculate_selection returns Weights (isin: weight)
    weights = strategy.calculate_selection(rebalance_date)
    
    if not weights:
        print("No stocks selected in the Bottom/Low/Low quadrant for Feb 2026.")
        return
        
    selected_isins = list(weights.keys())
    
    # Map ISINs to Industries
    results = []
    for isin in selected_isins:
        ind = dh.isin_to_industry.get(isin, "Unknown")
        group = dh.isin_to_group.get(isin, "Unknown")
        results.append({'isin': isin, 'industry': ind, 'group': group})
        
    df = pd.DataFrame(results)
    unique_industries = df['industry'].unique()
    
    print("\n" + "="*50)
    print("INDUSTRIES IN BOTTOM/LOW/LOW (FAILURE REGIME)")
    print(f"REBALANCE DATE: {rebalance_date}")
    print("="*50)
    for i, ind in enumerate(unique_industries, 1):
        stocks_count = len(df[df['industry'] == ind])
        print(f"{i}. {ind} ({stocks_count} stocks)")
    print("="*50)
    
    # Also print the specific stocks for clarity
    print("\nSPECIFIC STOCKS SELECTED FOR SHORTING:")
    print(df.to_string(index=False))
    print("="*50)

if __name__ == "__main__":
    get_failure_industries()
