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

class MCPSStrategy(ContrarianBreadthStrategy):
    """
    Variation of the Champion strategy using Market Cap Per Shareholder (MCPS)
    instead of simple Shareholder Decrease for Industry Group and Industry breadths.
    """
    def __init__(self, data_handler, group_thresh=0.50, ind_thresh=0.50, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.industry_group_top_pct = group_thresh
        self.industry_decrease_min_pct = ind_thresh

    def calculate_selection(self, date: pd.Timestamp) -> dict:
        actual_calc_date = date
        all_dates = self.dh.get_all_dates()
        
        # 1. Define Universe (Top 1000)
        universe = self.dh.get_universe(actual_calc_date, size=self.universe_size)
        if universe.empty: return {}
        
        # 2. MCPS Calculation
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
        
        # Calculate MCPS Increase
        merged['mcps_increase'] = (merged['current_mc']/merged['curr_sh']) > (merged['prev_mc']/merged['prev_sh'])
        merged['mcps_increase'] = merged['mcps_increase'].astype(int)
        
        merged['group'] = merged['isin'].map(self.dh.isin_to_group)
        merged['industry'] = merged['isin'].map(self.dh.isin_to_industry)
        
        # --- BREADTH FILTERS ---
        
        # 3. Industry Group Breadth Filter
        group_breadth = merged.groupby('group')['mcps_increase'].mean()
        valid_groups = group_breadth[group_breadth >= self.industry_group_top_pct].index
        
        # 4. Industry Breadth Filter
        ind_breadth = merged[merged['group'].isin(valid_groups)].groupby('industry')['mcps_increase'].mean()
        qualified_industries = ind_breadth[ind_breadth >= self.industry_decrease_min_pct].index.tolist()
        
        if not qualified_industries: return {}
        
        # 5. RSNP Ranking (Industry level)
        b_prices = self.dh.top_1000_bench
        lookback_start = actual_calc_date - pd.Timedelta(days=365)
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        # Robust Price Maps
        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-30:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
        
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 6. RSI Filter (Stock Level)
        rsi_passed_isins = []
        if not self.rsi_cache.empty:
            valid_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
            if valid_dates:
                rsi_date = max(valid_dates)
                rsis = self.rsi_cache.loc[rsi_date]
                rsi_passed_isins = rsis[rsis >= self.rsi_threshold].index.tolist()
        
        if not rsi_passed_isins: return {}
        
        # 7. Final Pick (Top Market Cap)
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            eligible_isins = [isin for isin in ind_isins if isin in rsi_passed_isins and isin in universe['isin'].values]
            ind_universe = universe[universe['isin'].isin(eligible_isins)].sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
        
        if not selected_isins: return {}
        num_found = len(selected_isins)
        w = min(0.10, 1.0 / num_found) if num_found < self.num_stocks else 1.0 / self.num_stocks
        return {isin: w for isin in selected_isins}

def run_mcps_sensitivity():
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
    
    group_thresholds = [0.30, 0.35, 0.40, 0.45, 0.50]
    ind_thresholds = [0.30, 0.40, 0.50, 0.60, 0.70]
    
    results = []
    
    print("\n--- Starting MCPS Sensitivity Analysis ---")
    total_runs = len(group_thresholds) * len(ind_thresholds)
    current_run = 0
    
    for g_t in group_thresholds:
        for i_t in ind_thresholds:
            current_run += 1
            print(f"\nRun {current_run}/{total_runs}: Group={g_t:.0%}, Ind={i_t:.0%}")
            
            port = Portfolio(10000000)
            strat = MCPSStrategy(dh, group_thresh=g_t, ind_thresh=i_t, min_history_years=0.0)
            strat.precompute_rsi(quarterly_dates)
            
            sim = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
            sim.run(start_date, end_date, strategy_func=strat.calculate_selection, rebalance_dates=quarterly_dates, verbose=False)
            
            stats = calculate_metrics(pd.DataFrame(port.nav_history))
            res = {
                'Group Thresh': f"{g_t:.0%}",
                'Ind Thresh': f"{i_t:.0%}",
                'CAGR': stats['CAGR'],
                'Sharpe': stats['Sharpe Ratio'],
                'Max Drawdown': stats['Max Drawdown']
            }
            results.append(res)
            # Immediate feedback print
            print(f"   RESULT: CAGR={res['CAGR']}, Sharpe={res['Sharpe']}, MDD={res['Max Drawdown']}")

    # Display Results Table
    df_res = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'Group Thresh':<12} | {'Ind Thresh':<12} | {'CAGR':<10} | {'Sharpe':<10} | {'Max Drawdown':<15}")
    print("-" * 80)
    for _, row in df_res.iterrows():
        print(f"{row['Group Thresh']:<12} | {row['Ind Thresh']:<12} | {row['CAGR']:<10} | {row['Sharpe']:<10} | {row['Max Drawdown']:<15}")
    print("="*80)

if __name__ == "__main__":
    run_mcps_sensitivity()
