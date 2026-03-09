
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from research_quarterly_count import QuarterlyCountStrategy, OptimizedQuarterlyCountStrategy, precompute_data
import warnings
warnings.filterwarnings('ignore')

def verify_equivalence():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    test_date = pd.Timestamp("2025-02-05")
    rebalance_dates = [test_date]
    
    # Original
    strat_orig = QuarterlyCountStrategy(dh, num_stocks=15, 
                                       industry_group_top_pct=0.50,
                                       industry_decrease_min_pct=0.35)
    sel_orig = strat_orig.calculate_selection(test_date)
    
    # Optimized
    cache = precompute_data(dh, rebalance_dates)
    strat_opt = OptimizedQuarterlyCountStrategy(dh, cache, num_stocks=15, 
                                               industry_group_top_pct=0.50,
                                               industry_decrease_min_pct=0.35)
    sel_opt = strat_opt.calculate_selection(test_date)
    
    print("\nTRANSITION AUDIT - FEB 2025")
    print("============================")
    print(f"Original Count: {len(sel_orig)}")
    print(f"Optimized Count: {len(sel_opt)}")
    
    orig_isins = sorted(list(sel_orig.keys()))
    opt_isins = sorted(list(sel_opt.keys()))
    
    common = set(orig_isins).intersection(set(opt_isins))
    print(f"Common Stocks: {len(common)}")
    
    if len(orig_isins) != len(opt_isins) or len(common) != len(orig_isins):
        print("\nDIFF:")
        print(f"Only in Original: {set(orig_isins) - set(opt_isins)}")
        print(f"Only in Optimized: {set(opt_isins) - set(orig_isins)}")
        
        # Check industry breadths
        # (This would require more printing inside the strategy)
        pass

if __name__ == "__main__":
    verify_equivalence()
