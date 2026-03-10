import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

from strategies.slt15_strategy import SLT15Strategy
from strategies.slt15_group_rank_strategy import SLT15GroupRankStrategy
from strategies.slt15_industry_rank_strategy import SLT15IndustryRankStrategy
from strategies.slt15_industry_median_rank_strategy import SLT15IndustryMedianRankStrategy

def get_selected_industries(strategy, date: pd.Timestamp, dh: DataHandler):
    selection = strategy.calculate_selection(date)
    if not selection:
        return []
    
    industries = set()
    for isin in selection.keys():
        if isin in dh.isin_to_industry:
            industries.add(dh.isin_to_industry[isin])
    return list(industries)

def run_extraction():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    print("Loading DataHandler...")
    dh.load_data()
    
    strategies = {
        "1. Original (Individual SH Change)": SLT15Strategy(dh, lookback_quarters=12, num_industries=10),
        "2. Group Breadth Rank": SLT15GroupRankStrategy(dh, lookback_quarters=12, num_industries=10),
        "3. Industry Breadth Rank": SLT15IndustryRankStrategy(dh, lookback_quarters=12, num_industries=10),
        "4. Industry Median SH Change Rank": SLT15IndustryMedianRankStrategy(dh, lookback_quarters=12, num_industries=10)
    }
    
    all_dates = dh.get_all_dates()
    
    target_dates = [pd.Timestamp("2025-02-15"), pd.Timestamp("2026-02-01")]
    eval_dates = []
    
    for td in target_dates:
        # Find closest available date on or after
        avail = [d for d in all_dates if d >= td]
        if avail:
            eval_dates.append(avail[0])
        else:
            # If no date after, just take the max date string for 2026-02
            # The exact max date is 2026-02-05
            eval_dates.append(all_dates[-1])
            
    # De-duplicate just in case
    eval_dates = list(dict.fromkeys(eval_dates))
    
    results = {}
    
    for date in eval_dates:
        print(f"\nEvaluating for rebalance date: {date.date()}")
        results[date.date()] = {}
        for name, strat in strategies.items():
            inds = get_selected_industries(strat, date, dh)
            results[date.date()][name] = inds
            
    print("\n" + "="*60)
    print("SELECTED INDUSTRIES BY VARIATION (12-QUARTER LOOKBACK)")
    print("="*60)
    
    for date, strats in results.items():
        print(f"\n--- Rebalance Date: {date} ---")
        for name, inds in strats.items():
            print(f"{name}:")
            if inds:
                for idx, ind in enumerate(sorted(inds), 1):
                    print(f"  {idx}. {ind}")
            else:
                print("  [No industries selected]")

if __name__ == "__main__":
    run_extraction()
