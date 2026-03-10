
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import datetime
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class QuarterlyCountStrategy(ContrarianBreadthStrategy):
    def __init__(self, data_handler, num_stocks=15, 
                 industry_group_top_pct=0.50, 
                 industry_decrease_min_pct=0.50):
        super().__init__(data_handler, num_stocks)
        # Override thresholds
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        
    def calculate_selection(self, date):
        # Override the specific selection logic but keep the skeleton
        # START: Universe Selection logic from Base Strategy
        calc_date = pd.Timestamp(date)
        
        # 1. Filter Universe (Liquid & Tradable)
        # Replicate universe construction from ContrarianBreadthStrategy/research_quarterly_count.py
        # because get_tradable_universe doesn't exist
        
        # We need actual metric date (often T-1 or T-7)
        # Using simple approach from original research script:
        metrics = self.dh.get_daily_metrics(calc_date)
        if metrics is None or metrics.empty:
            return []
            
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
        # Add basic liquidity check if needed (or assume top 500 MC are liquid enough for research)
        # For speed/simplicity in this optimized script, we stick to Top 500 MC.
        
        if universe.empty:
            return []
            
        # 2. RSNP Filter (Relative Strength vs Nifty)
        # Calculate RSNP for all stocks in universe
        # We need 1-year returns for stocks and Nifty
        start_date_1y = calc_date - pd.DateOffset(years=1)
        
        # Get prices
        prices = self.dh.get_stock_prices(universe.index.tolist(), start_date_1y, calc_date)
        nifty_prices = self.dh.get_nifty_prices(start_date_1y, calc_date)
        
        if prices.empty or nifty_prices.empty:
            return []
            
        # Calculate Returns
        stock_rets = (prices.iloc[-1] / prices.iloc[0]) - 1
        nifty_ret = (nifty_prices.iloc[-1] / nifty_prices.iloc[0]) - 1
        
        rsnp = stock_rets - nifty_ret
        
        # Filter for RSNP > 0
        rsnp_pass = rsnp[rsnp > 0].index.tolist()
        
        if not rsnp_pass:
            return []
            
        # 3. Shareholder Breadth Signal (QUARTERLY COUNT LOGIC)
        # Get latest shareholding data
        sh_data = self.dh.shareholding_df.copy()
        if 'date' not in sh_data.columns:
             try:
                 sh_data['date'] = pd.to_datetime(sh_data['quarter'])
             except:
                 pass
        
        valid_sh = sh_data[sh_data['date'] <= calc_date].copy()
        
        # Filter for universe
        valid_sh = valid_sh[valid_sh['isin'].isin(rsnp_pass)]
        
        # We need to sort by date for each ISIN to get sequential quarters
        valid_sh = valid_sh.sort_values(['isin', 'date'], ascending=[True, False]) # Newest first
        
        # We need the last 5 quarters to calculate 4 sequential changes?
        # Q0 vs Q-1, Q-1 vs Q-2, Q-2 vs Q-3, Q-3 vs Q-4.
        # So we need top 5 rows per ISIN.
        recent_sh = valid_sh.groupby('isin').head(5).copy()
        
        # Sort back to chronological for shift to work logically (Oldest to Newest)
        recent_sh = recent_sh.sort_values(['isin', 'date'], ascending=[True, True])
        
        # Now count decreases.
        recent_sh['prev_sh_held'] = recent_sh.groupby('isin')['total_shareholders'].shift(1) # Shift down to compare t vs t-1
        recent_sh['is_decrease'] = recent_sh['total_shareholders'] < recent_sh['prev_sh_held']
        
        # Drop the first row (NaN)
        recent_analysis = recent_sh.dropna(subset=['prev_sh_held'])
        
        # Count decreases per ISIN (Sum of True)
        decrease_counts = recent_analysis.groupby('isin')['is_decrease'].sum()
        # Count total valid comparisons (should be 4 ideally)
        total_counts = recent_analysis.groupby('isin')['is_decrease'].count()
        
        # Calculate ratio: Decreases / Total Checks
        decrease_ratio = decrease_counts / total_counts
        
        # Calculate Industry Aggregates using this Ratio
        # Map ISIN to Industry
        decrease_df = pd.DataFrame({'ratio': decrease_ratio})
        decrease_df['industry'] = decrease_df.index.map(lambda x: self.dh.get_industry(x))
        decrease_df['group'] = decrease_df.index.map(lambda x: self.dh.get_industry_group(x)) # Assuming accessible
        
        # If group not accessible via single call, we might need a workaround. 
        # But let's assume get_industry_group works or we use the mapping df.
        # Actually base strategy uses `self.dh.master_df`.
        master = self.dh.master_df
        decrease_df = decrease_df.join(master[['Industry', 'Macro-Economic Sector']], on='isin')
        # Rename for clarity
        decrease_df.rename(columns={'Industry': 'ind_name', 'Macro-Economic Sector': 'group_name'}, inplace=True)
        
        # Calculate Scores
        # Group Score = Average Ratio of stocks in Group? Or % of stocks with Ratio > X?
        # The logic: "Percentage of Stocks in Group/Industry where Decreases > Threshold?"
        # OR "Average Decrease Count per Group"?
        
        # The Prompt implies: "Percentage of STOCKHOLDERS decreased" -> This was the definition of "Shareholder Decrease".
        # Now we have a NEW metric: "Quarterly Decrease Ratio" (0, 0.25, 0.5, 0.75, 1.0).
        # We need to Aggregate this.
        # Official Strategy: % of stocks where (Q0 < Q4).
        # New Strategy: % of stocks where (Decrease Ratio > ??) OR Average Decrease Ratio?
        
        # Let's stick to the structure:
        # A stock is "Qualified" if its Decrease Ratio >= 0.5 (i.e. Decreased in at least 2 quarters).
        # Then we calculate % of Qualified Stocks in Industry.
        
        qualified_stock_threshold = 0.5 # Default: Needs to decrease in 2/4 quarters to be a "Declining Stock"
        
        decrease_df['is_declining'] = decrease_df['ratio'] >= qualified_stock_threshold
        
        # Industry Level
        ind_stats = decrease_df.groupby('ind_name')['is_declining'].mean() # % of stocks decling
        
        # Group Level
        grp_stats = decrease_df.groupby('group_name')['is_declining'].mean()
        
        # Filter Industries
        # 1. Group must be in Top X% (Relative) OR > X% (Absolute)?
        # Original: Top 50% of Groups.
        # Let's use Relative Ranking for Groups.
        grp_rank = grp_stats.rank(pct=True)
        passing_groups = grp_rank[grp_rank >= (1 - self.industry_group_top_pct)].index.tolist()
        
        # 2. Industry must have > Y% stocks declining (Absolute)
        passing_inds = ind_stats[ind_stats >= self.industry_decrease_min_pct].index.tolist()
        
        # Final Candidates
        final_candidates = decrease_df[
            (decrease_df['group_name'].isin(passing_groups)) &
            (decrease_df['ind_name'].isin(passing_inds)) &
            (decrease_df['is_declining']) # Stock itself must be declining
        ].index.tolist()
        
        return final_candidates

def run_research():
    print("Loading Data...")
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    rebalance_dates = pd.date_range(start_date, end_date, freq='QE')
    
    # Run Official for Baseline (just print hardcoded from previous run if we want speed, but running it is safer)
    print("\nRunning Official Strategy (YoY) for Baseline...")
    strat0 = ContrarianBreadthStrategy(dh, num_stocks=15)
    port0 = Portfolio(10000000)
    eng0 = SimEngine(dh, port0, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng0.run(start_date, end_date, strat0.calculate_selection, rebalance_dates, verbose=False)
    res0 = calculate_metrics(pd.DataFrame(port0.nav_history))
    
    print(f"Official Baseline: CAGR={res0['CAGR']}, MaxDD={res0['Max Drawdown']}")
    
    configs = [
        (0.40, 0.40), # Looser
        (0.40, 0.50), # Looser Group
        (0.50, 0.40), # Looser Ind
        (0.50, 0.50)  # Standard (Retest with suppressed warnings)
    ]
    
    print("\nRunning Sensitivity Grid...")
    print(f"{'Config (Grp/Ind)':<20} | {'CAGR':>10} | {'MaxDD':>10} | {'Sharpe':>10}")
    print("-" * 60)
    
    for g, i in configs:
        strat = QuarterlyCountStrategy(dh, num_stocks=15, 
                                      industry_group_top_pct=g, # Pct to KEEP (0.4 means top 40%)
                                      industry_decrease_min_pct=i)
        
        port = Portfolio(10000000)
        eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
        eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
        res = calculate_metrics(pd.DataFrame(port.nav_history))
        
        print(f"Grp {g:.0%}/Ind {i:.0%}{'':<8} | {res['CAGR']:>10} | {res['Max Drawdown']:>10} | {res['Sharpe Ratio']:>10}")

if __name__ == "__main__":
    run_research()
