
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics
import warnings
import time

# --- OPTIMIZED STRATEGY ---
class OptimizedQuarterlyCountStrategy(ContrarianBreadthStrategy):
    def __init__(self, data_handler, cache_data, num_stocks=10, 
                 industry_group_top_pct=0.50, 
                 industry_decrease_min_pct=0.50):
        # Parameters standardized for Quarterly Count Research (10 Stocks)
        super().__init__(data_handler, num_stocks)
        self.cache_data = cache_data
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.max_per_industry = 3
        self.rsi_threshold = 40
        self.rsnp_threshold = 0.4

    def calculate_selection(self, date: pd.Timestamp) -> pd.Series:
        # Standard optimized selection logic
        calc_date = pd.Timestamp(date)
        if calc_date not in self.cache_data or self.cache_data[calc_date] is None:
            return {}
            
        cache = self.cache_data[calc_date]
        universe_isins = cache['universe_isins']
        isin_scores = cache['isin_scores'] 
        ind_rsnp_map = cache['ind_rsnp_map']
        
        # 1. Industry Group Score
        if isin_scores.empty: return {}
        group_stats = isin_scores.groupby('group')['decrease_count'].agg(['sum', 'count']).reset_index()
        # Point-to-Point: decrease_count is 0 or 1 per ISIN
        group_stats['score_pct'] = group_stats['sum'] / group_stats['count']
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('score_pct', ascending=False).head(num_to_pick)['group'].tolist()
        
        # 2. Industry Score
        ind_in_groups = isin_scores[isin_scores['group'].isin(top_groups)]
        if ind_in_groups.empty: return {}
        ind_stats = ind_in_groups.groupby('industry')['decrease_count'].agg(['sum', 'count']).reset_index()
        # Point-to-Point
        ind_stats['score_pct'] = ind_stats['sum'] / ind_stats['count']
        
        qualified_industries = ind_stats[ind_stats['score_pct'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 3. RSNP
        industry_rsnp = []
        for ind in qualified_industries:
            rsnp = ind_rsnp_map.get(ind, 0.0)
            industry_rsnp.append({'industry': ind, 'rsnp': rsnp})
            
        # Tie-breaker: sort by rsnp desc, then industry name asc for stability
        ind_ranked = pd.DataFrame(industry_rsnp).sort_values(['rsnp', 'industry'], ascending=[False, True])
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        if ind_ranked.empty: return {}
        
        # 4. RSI & Final Selection
        rsi_lookup_date = max([d for d in self.rsi_cache.index if d <= calc_date])
        # Preserving original head(500) order (MC-desc) during RSI filter
        rsis = self.rsi_cache.loc[rsi_lookup_date]
        passed_isins = [i for i in universe_isins if rsis.get(i, 0) > self.rsi_threshold]
        
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_stocks = [isin for isin in passed_isins if self.dh.isin_to_industry.get(isin) == ind]
            for isin in ind_stocks[:self.max_per_industry]:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break

        if not selected_isins: return {}
        w = 1.0 / len(selected_isins)
        return {isin: w for isin in selected_isins}

# --- PRE-COMPUTATION HELPER ---
def precompute_data(dh, rebalance_dates):
    print("Pre-computing data for all rebalance dates (Breadth & RSNP)...")
    cache_data = {}
    
    sh_data = dh.shareholding_df.copy()
    if 'date' not in sh_data.columns:
        sh_data['date'] = pd.to_datetime(sh_data['quarter'], errors='coerce')
    sh_data = sh_data.dropna(subset=['date']).sort_values(['isin', 'date'], ascending=[True, False])
    
    # POINT-TO-POINT: Most Recent vs 4 Quarters Ago (1 Year)
    sh_data['prev_sh_4q'] = sh_data.groupby('isin')['total_shareholders'].shift(-4)
    sh_data['is_decrease'] = (sh_data['total_shareholders'] < sh_data['prev_sh_4q']).astype(float)
    
    all_dates = dh.get_all_dates()
    
    for reb_date in rebalance_dates:
        signal_date = reb_date - pd.Timedelta(days=7)
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        lookback_date = actual_signal_date - pd.Timedelta(days=365)
        actual_lookback_start = max([d for d in all_dates if d <= lookback_date])
        
        # 1. Universe (Top 1000 MC + Liquidity)
        metrics = dh.get_daily_metrics(actual_signal_date)
        if metrics is None or metrics.empty: 
            cache_data[reb_date] = None
            continue
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        
        rolling_start = actual_signal_date - pd.Timedelta(days=40)
        liq_window = [d for d in all_dates if rolling_start <= d <= actual_signal_date][-21:]
        liq_df = dh.price_df[dh.price_df['date'].isin(liq_window)]
        avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * 0.00005)] 
        univ_isins = universe['isin'].tolist()
        
        # 2. Shareholder Scores (Calculated on ALL stocks for true Breadth)
        relevant_sh = sh_data[sh_data['date'] <= actual_signal_date]
        if relevant_sh.empty:
            isin_scores = pd.DataFrame(columns=['isin', 'decrease_count', 'group', 'industry'])
        else:
            # Point-to-Point: Most recent record for EACH ISIN in the database
            top_sh = relevant_sh.groupby('isin').head(1)
            if top_sh.empty:
                isin_scores = pd.DataFrame(columns=['isin', 'decrease_count', 'group', 'industry'])
            else:
                isin_scores = top_sh[['isin', 'is_decrease']].rename(columns={'is_decrease': 'decrease_count'})
                isin_scores['group'] = isin_scores['isin'].map(dh.isin_to_group)
                isin_scores['industry'] = isin_scores['isin'].map(dh.isin_to_industry)
        
        # 3. Vectorized RSNP for ALL INDUSTRIES
        def get_all_prices(target_date):
            window = [d for d in all_dates if d <= target_date][-30:]
            subset = dh.price_df[dh.price_df['date'].isin(window)]
            if subset.empty: return pd.Series()
            return subset.sort_values('date').groupby('isin')['close'].last()
            
        p_end = get_all_prices(actual_signal_date)
        p_start = get_all_prices(actual_lookback_start)
        common = p_end.index.intersection(p_start.index)
        
        b_subset_end = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_signal_date]
        b_subset_start = dh.top_1000_bench[dh.top_1000_bench['date'] <= actual_lookback_start]
        bench_ret = (b_subset_end['index_value'].iloc[-1] / b_subset_start['index_value'].iloc[-1]) - 1 if not (b_subset_end.empty or b_subset_start.empty) else 0.0
        
        beaten = ((p_end.loc[common] / p_start.loc[common]) - 1 > bench_ret).astype(int)
        beaten_df = beaten.to_frame('beaten')
        beaten_df['industry'] = beaten_df.index.map(dh.isin_to_industry)
        ind_rsnp_stats = beaten_df.groupby('industry')['beaten'].agg(['sum', 'count']).reset_index()
        ind_rsnp_map = (ind_rsnp_stats['sum'] / ind_rsnp_stats['count']).set_axis(ind_rsnp_stats['industry']).to_dict()
        
        cache_data[reb_date] = { 'universe_isins': univ_isins, 'isin_scores': isin_scores, 'ind_rsnp_map': ind_rsnp_map }
    return cache_data

def run_quarterly_count_research():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date, end_date = "2017-05-15", "2026-02-05"
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date): rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    cache_data = precompute_data(dh, rebalance_dates)

    print("\nRunning Optimized Grid Search (7x7) - 15 Stocks PT-TO-PT CHAMPION...")
    warnings.filterwarnings('ignore')
    thresholds = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    results = []
    output_file = repo_root / "quarterly_sensitivity_results_ptp_champion.csv"
    
    start_all = time.time()
    for g_pct in thresholds:
        for i_pct in thresholds:
            t1 = time.time()
            strat = OptimizedQuarterlyCountStrategy(dh, cache_data, num_stocks=15, 
                                                   industry_group_top_pct=g_pct,
                                                   industry_decrease_min_pct=i_pct)
            port = Portfolio(10000000)
            eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
            eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
            res = calculate_metrics(pd.DataFrame(port.nav_history))
            results.append({
                "Mode": "Qtly Count", "Grp_Thresh": g_pct, "Ind_Thresh": i_pct,
                "CAGR": res['CAGR'], "MaxDD": res['Max Drawdown'], "Sharpe": res['Sharpe Ratio']
            })
            print(f"Grp {g_pct:.0%}/Ind {i_pct:.0%}: CAGR {res['CAGR']} ({time.time()-t1:.1f}s)")
            pd.DataFrame(results).to_csv(output_file, index=False)

    print(f"\nGrid search complete in {(time.time()-start_all)/60:.1f} minutes.")
    final_df = pd.DataFrame(results)
    final_df['CAGR_num'] = final_df['CAGR'].str.rstrip('%').astype(float)
    print("\nTOP RESULTS:")
    print(final_df.sort_values('CAGR_num', ascending=False).head(10).to_string(index=False))

if __name__ == "__main__":
    run_quarterly_count_research()
