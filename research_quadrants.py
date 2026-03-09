
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class QuadrantStrategy(ContrarianBreadthStrategy):
    """
    Flexible strategy for 3D sensitivity analysis.
    group_mode: 'top' or 'bottom'
    industry_mode: 'high' (>= threshold) or 'low' (< threshold)
    rsnp_mode: 'high' (>= 0.40) or 'low' (< 0.40)
    """
    def __init__(self, data_handler, group_mode='top', industry_mode='high', rsnp_mode='high', **kwargs):
        super().__init__(data_handler, **kwargs)
        self.group_mode = group_mode
        self.industry_mode = industry_mode
        self.rsnp_mode = rsnp_mode

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns target weights for the portfolio, identical to Champion but with mode switches."""
        # 1. Calculation dates (1 week prior to rebalance)
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # 2. Market Universe & Liquidity Filtering
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        # Top 1000 by Market Cap
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
        # Liquidity Filter: Avg traded value last 21 trading days > 0.005% of MC
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liquidity_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        
        if len(liquidity_window) < 10:
             avg_liq = universe[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        if universe.empty: return {}
        
        # 3. Shareholder Filter (Two-Tier)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        if self.min_industry_size > 0:
            ind_counts = sh_trend['industry'].value_counts()
            valid_inds = ind_counts[ind_counts >= self.min_industry_size].index
            sh_trend = sh_trend[sh_trend['industry'].isin(valid_inds)]
            
        if sh_trend.empty: return {}
        
        # (i) Industry Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        
        # QUADRANT SWITCH: Group Selection
        if self.group_mode == 'top':
            selected_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        else: # 'bottom'
            selected_groups = group_stats.sort_values('mean', ascending=True).head(num_to_pick)['group'].tolist()
            
        # (ii) Industry Filter
        ind_in_groups = sh_trend[sh_trend['group'].isin(selected_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        
        # QUADRANT SWITCH: Industry Breadth
        if self.industry_mode == 'high':
            qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        else: # 'low'
            qualified_industries = ind_stats[ind_stats['mean'] < self.industry_decrease_min_pct]['industry'].tolist()
            
        if not qualified_industries: return {}
        
        # 4. RSNP Ranking (Industry Breadth vs Top 1000)
        # Benchmark Return
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        # Robust Price Maps
        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-self.price_lookback_days:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins, eligible = 0, 0
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
        
        # QUADRANT SWITCH: RSNP Filter
        if self.rsnp_mode == 'high':
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        else: # 'low'
            ind_ranked = ind_ranked[ind_ranked['rsnp'] < self.rsnp_threshold]
            
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 5. RSI Entry Filter
        if self.rsi_threshold > 0 and not self.rsi_cache.empty:
             valid_cache_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
             if valid_cache_dates:
                 rsi_lookup_date = max(valid_cache_dates)
                 univ_isins = universe['isin'].tolist()
                 valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
                 
                 if valid_isins:
                     rsis = self.rsi_cache.loc[rsi_lookup_date, valid_isins]
                     passed_isins = rsis[rsis > self.rsi_threshold].index.tolist()
                     universe = universe[universe['isin'].isin(passed_isins)]
        
        if universe.empty: return {}
 
        # 6. Stock Selection
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
            ind_universe = ind_universe.sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
                    
        if not selected_isins: return {}
        
        # 7. Weighting
        num_final = len(selected_isins)
        if num_final >= self.num_stocks:
            w = 1.0 / num_final
        else:
            w = max(0.0667, 1.0 / num_final) if num_final > 0 else 0
            w = min(0.10, w)
            
        return {isin: w for isin in selected_isins}

def run_quadrant_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_trading_dates = dh.get_all_dates()
    
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    # 2x2x2 Matrix = 8 combinations
    combinations = [
        ('Champion', 'Baseline', 'Baseline'), # Reference
        ('Top', 'High', 'High'), ('Top', 'High', 'Low'),
        ('Top', 'Low', 'High'), ('Top', 'Low', 'Low'),
        ('Bottom', 'High', 'High'), ('Bottom', 'High', 'Low'),
        ('Bottom', 'Low', 'High'), ('Bottom', 'Low', 'Low')
    ]
    
    results = []
    for g_mode, i_mode, r_mode in combinations:
        print(f"\nEvaluating: Group={g_mode}, Industry={i_mode}, RSNP={r_mode}...")
        
        if i_mode == 'Baseline':
             strategy = ContrarianBreadthStrategy(
                 dh, num_stocks=15, max_per_industry=3, rsnp_threshold=0.40
             )
        else:
             strategy = QuadrantStrategy(
                 dh, group_mode=g_mode.lower(), industry_mode=i_mode.lower(), rsnp_mode=r_mode.lower(),
                 num_stocks=15, max_per_industry=3, rsnp_threshold=0.40
             )
        
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date="2017-05-15", end_date="2026-02-05", 
            strategy_func=strategy.calculate_selection, rebalance_dates=rebalance_dates,
            verbose=False
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        if not nav_df.empty:
            stats = calculate_metrics(nav_df)
            results.append({
                'Group': g_mode,
                'Breadth': i_mode,
                'RSNP': r_mode,
                'CAGR': stats['CAGR'],
                'Abs. Return': stats['Absolute Return'],
                'Max Drawdown': stats['Max Drawdown'],
                'Final NAV': portfolio.nav_history[-1]['nav']
            })
            
    summary_df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("3D SENSITIVITY ANALYSIS SUMMARY (Group x Breadth x RSNP)")
    print("="*80)
    print(summary_df.head(20).to_string(index=False))
    print("="*80)
    summary_df.to_csv(repo_root / "outputs/sensitivity_3d_summary.csv", index=False)

if __name__ == "__main__":
    run_quadrant_analysis()

if __name__ == "__main__":
    run_quadrant_analysis()
