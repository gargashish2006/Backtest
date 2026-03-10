import pandas as pd
import numpy as np
import warnings
from pathlib import Path
from typing import Dict, List
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class MCPSRankingStrategy(ContrarianBreadthStrategy):
    """
    Variation that ranks industries based on MCPS Breadth % 
    instead of RSNP.
    """
    def __init__(self, data_handler, group_thresh=0.50, ind_thresh=0.50, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.industry_group_top_pct = group_thresh
        self.industry_decrease_min_pct = ind_thresh

    def calculate_selection(self, date: pd.Timestamp) -> dict:
        actual_calc_date = date
        all_dates = self.dh.get_all_dates()
        
        universe = self.dh.get_universe(actual_calc_date, size=self.universe_size)
        if universe.empty: return {}
        
        lookback_quarters = self.shareholder_lookback_quarters
        lookback_days = lookback_quarters * 91
        lookback_date_target = actual_calc_date - pd.Timedelta(days=lookback_days)
        valid_prev_dates = [d for d in all_dates if d <= lookback_date_target]
        if not valid_prev_dates: return {}
        prev_date = max(valid_prev_dates)
        
        prev_universe_data = self.dh.price_df[self.dh.price_df['date'] == prev_date]
        curr_universe_data = universe[['isin', 'mc']].copy()
        
        sh_trend = self.dh.get_shareholder_trend(actual_calc_date, lookback_quarters=lookback_quarters)
        if sh_trend.empty: return {}
        
        merged = sh_trend[['isin', 'curr_sh', 'prev_sh']].merge(
            curr_universe_data, on='isin', how='inner'
        ).rename(columns={'mc': 'current_mc'})
        
        merged = merged.merge(
            prev_universe_data[['isin', 'mc']], on='isin', how='inner'
        ).rename(columns={'mc': 'prev_mc'})
        
        if merged.empty: return {}
        
        # Signal: MCPS Increase
        merged['mcps_increase'] = (merged['current_mc']/merged['curr_sh']) > (merged['prev_mc']/merged['prev_sh'])
        merged['mcps_increase'] = merged['mcps_increase'].astype(int)
        
        merged['group'] = merged['isin'].map(self.dh.isin_to_group)
        merged['industry'] = merged['isin'].map(self.dh.isin_to_industry)
        
        # 1. Group Filter
        group_breadth = merged.groupby('group')['mcps_increase'].mean()
        valid_groups = group_breadth[group_breadth >= self.industry_group_top_pct].index
        
        # 2. Industry Breadth & Ranking
        ind_breadth = merged[merged['group'].isin(valid_groups)].groupby('industry')['mcps_increase'].mean()
        
        # NEW: Filter and Rank by Industry MCPS Breadth % directly
        qualified_ind_breadth = ind_breadth[ind_breadth >= self.industry_decrease_min_pct]
        if qualified_ind_breadth.empty: return {}
        
        # Sort industries by the Breadth % (The requested change)
        ind_ranked = qualified_ind_breadth.sort_values(ascending=False).to_frame(name='mcps_breadth').reset_index()
        
        # 3. RSI Filter (Stock Level)
        rsi_passed_isins = []
        if not self.rsi_cache.empty:
            valid_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
            if valid_dates:
                rsi_date = max(valid_dates)
                rsis = self.rsi_cache.loc[rsi_date]
                rsi_passed_isins = rsis[rsis >= self.rsi_threshold].index.tolist()
        
        if not rsi_passed_isins: return {}
        
        # 4. Selection (Top Market Cap within Top Industries)
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            eligible_isins = [isin for isin in ind_isins if isin in rsi_passed_isins and isin in universe['isin'].values]
            
            # Additional constraint: The stock ITSSELF should have MCPS increase? 
            # (Following Champion logic where selected stocks must match the breadth criteria)
            stock_specific_mcps = merged[merged['isin'].isin(eligible_isins) & (merged['mcps_increase'] == 1)]['isin'].tolist()
            
            ind_universe = universe[universe['isin'].isin(stock_specific_mcps)].sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
        
        if not selected_isins: return {}
        num_found = len(selected_isins)
        w = min(0.10, 1.0 / num_found) if num_found < self.num_stocks else 1.0 / self.num_stocks
        return {isin: w for isin in selected_isins}

def run_mcps_ranking_comparison():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    all_dates = dh.get_all_dates()
    
    quarterly_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in quarterly_dates:
                        quarterly_dates.append(reb)
    quarterly_dates.sort()
    
    # Run Comparison
    print("\n--- Running MCPS Breadth Ranking Variation ---")
    port_r = Portfolio(10000000)
    strat_r = MCPSRankingStrategy(dh, group_thresh=0.40, ind_thresh=0.50, min_history_years=0.0)
    strat_r.precompute_rsi(quarterly_dates)
    sim_r = SimEngine(dh, port_r, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    sim_r.run(start_date, end_date, strategy_func=strat_r.calculate_selection, rebalance_dates=quarterly_dates)
    stats_r = calculate_metrics(pd.DataFrame(port_r.nav_history))
    
    print("\n" + "="*45)
    print(f"{'Metric':<15} | {'MCPS (Breadth Rank)':<25}")
    print("-" * 45)
    for m in ['CAGR', 'Sharpe Ratio', 'Max Drawdown']:
        print(f"{m:<15} | {stats_r[m]:<25}")
    print("="*45)

if __name__ == "__main__":
    run_mcps_ranking_comparison()
