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

class MCPSIndustryRankingStrategy(ContrarianBreadthStrategy):
    """
    Strategy that ranks industries based on MCPS Breadth percentage.
    - Universe: Top 1000 by Market Cap.
    - Selection: Top industries by MCPS Breadth, max 3 stocks per industry, total 15.
    - Stocks must have self-MCPS increase.
    - Strictly Fundamental Snapshots for signals.
    """
    def __init__(self, data_handler, **kwargs):
        super().__init__(data_handler, **kwargs)
        # Defaults match Champion
        self.num_stocks = 15
        self.max_per_industry = 3
        self.universe_size = 1000
        self.liquidity_threshold_pct = 0.00005

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        all_dates = self.dh.get_all_dates()
        
        # 1. Fundamental Timing Lag for Shareholder Data
        m, y = date.month, date.year
        if m == 5: q_code = f"Mar-{y}"; prev_q = f"Mar-{y-1}"
        elif m == 8: q_code = f"Jun-{y}"; prev_q = f"Jun-{y-1}"
        elif m == 11: q_code = f"Sep-{y}"; prev_q = f"Sep-{y-1}"
        else: q_code = f"Dec-{y-1}"; prev_q = f"Dec-{y-2}"
        
        # Market Cap: 1 week before rebalance
        curr_mc_date = max([d for d in all_dates if d <= (date - pd.Timedelta(days=7))])
        prev_mc_date = max([d for d in all_dates if d <= (curr_mc_date - pd.Timedelta(days=365))])
        
        # 2. Universe & Liquidity (On Rebalance Date)
        universe = self.dh.get_universe(date, size=self.universe_size)
        if universe.empty: return {}
        
        liquidity_window = [d for d in all_dates if d <= date][-21:]
        if len(liquidity_window) >= 10:
            liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
            avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
            universe = pd.merge(universe, avg_liq, on='isin', how='left')
            universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        if universe.empty: return {}
        
        # 3. MCPS Signal calculation (SH from quarter, MC from 1 week before RB)
        def get_mcps_data(target_q, mc_date):
            sh = self.dh.shareholding_df
            sh_slice = sh[sh['quarter'] == target_q][['isin', 'total_shareholders']]
            price_slice = self.dh.get_daily_metrics(mc_date)[['isin', 'mc']]
            merged = pd.merge(sh_slice, price_slice, on='isin', how='inner')
            merged['mcps'] = merged['mc'] / merged['total_shareholders']
            return merged[['isin', 'mcps']]
        
        try:
            curr_mcps = get_mcps_data(q_code, curr_mc_date).rename(columns={'mcps': 'mcps_curr'})
            prev_mcps = get_mcps_data(prev_q, prev_mc_date).rename(columns={'mcps': 'mcps_prev'})
            mcps_trend = pd.merge(curr_mcps, prev_mcps, on='isin', how='inner')
            mcps_trend['mcps_inc'] = (mcps_trend['mcps_curr'] > mcps_trend['mcps_prev']).astype(int)
        except:
            return {}

        mcps_trend['industry'] = mcps_trend['isin'].map(self.dh.isin_to_industry)
        
        # 4. Industry Ranking
        ind_breadth = mcps_trend.groupby('industry')['mcps_inc'].mean().sort_values(ascending=False).to_frame(name='breadth').reset_index()
        
        # 5. Selection
        selected_isins = []
        # Filter: Stock must be in Top 1000/Liquid universe AND have self-MCPS increase
        passed_mcps_isins = mcps_trend[mcps_trend['mcps_inc'] == 1]['isin'].tolist()
        eligible_universe = universe[universe['isin'].isin(passed_mcps_isins)]
        
        for ind in ind_breadth['industry']:
            if len(selected_isins) >= self.num_stocks: break
            
            ind_stocks = eligible_universe[eligible_universe['isin'].map(self.dh.isin_to_industry) == ind]
            ind_stocks = ind_stocks.sort_values('mc', ascending=False) # Pick Largest
            
            top_for_ind = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
        
        if not selected_isins: return {}
        
        # Equal Weight
        w = 1.0 / len(selected_isins)
        return {isin: w for isin in selected_isins}

def run_mcps_ranking_strategy():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-02-05"
    all_dates = dh.get_all_dates()

    # Rebalance Dates
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in rebalance_dates: rebalance_dates.append(reb)
    rebalance_dates.sort()

    print("\n" + "="*60)
    print("RUNNING MCPS INDUSTRY RANKING STRATEGY")
    print("="*60)

    port = Portfolio(10000000)
    # Using defaults: 15 stocks, max 3 per industry
    strat = MCPSIndustryRankingStrategy(dh, min_history_years=0.0)
    
    # Pre-compute RSI for Champion-style exits if needed
    strat.precompute_rsi(rebalance_dates)

    sim = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    sim.run(start_date, end_date, strategy_func=strat.calculate_selection, rebalance_dates=rebalance_dates)
    
    stats = calculate_metrics(pd.DataFrame(port.nav_history))
    
    print("\n" + "="*60)
    print(f"RESULTS: {start_date} to {end_date}")
    print("-" * 60)
    for k, v in stats.items():
        print(f"{k:<20} : {v}")
    print("="*60)

if __name__ == "__main__":
    run_mcps_ranking_strategy()
