
import pandas as pd
import warnings
from typing import Dict
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class GroupSortStrategy(ContrarianBreadthStrategy):
    """
    Variation:
    1. Industry Group > 50% decrease (Same)
    2. Industry > 50% decrease (Same)
    3. RSNP > 0.5 (Stricter)
    4. SORTING: By Group Score Descending (Instead of RSNP)
    """
    def __init__(self, data_handler, num_stocks=15, **kwargs):
        super().__init__(data_handler, num_stocks, **kwargs)
        self.rsnp_threshold = 0.5 # Stricter
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # Copied & Modified from ContrarianBreadthStrategy
        
        # 1. Calculation dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # 2. Market Universe & Liquidity
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
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
        
        # 3. Shareholder Filter
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # (i) Industry Group Filter
        group_stats = sh_trend.groupby('group')['decreased'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        if group_stats.empty: return {}
        
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('mean', ascending=False).head(num_to_pick)['group'].tolist()
        
        # Capture Group Scores for Sorting later
        group_score_map = dict(zip(group_stats['group'], group_stats['mean']))
        
        # (ii) Industry Filter
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 4. RSNP Ranking
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-self.price_lookback_days:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)
        
        industry_data = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            # Get Group for this Industry (optimization: take first isin)
            grp = self.dh.isin_to_group.get(ind_isins[0], "Unknown")
            
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            
            if eligible > 0:
                rsnp = wins/eligible
                # Filter by RSNP threshold (0.5)
                if rsnp >= self.rsnp_threshold:
                    industry_data.append({
                        'industry': ind, 
                        'rsnp': rsnp,
                        'group_score': group_score_map.get(grp, 0) # Add Group Score
                    })
                
        if not industry_data: return {}
        
        ind_ranked = pd.DataFrame(industry_data)
        
        # MODIFIED SORTING LOGIC:
        # Sort by Group Score Descending, then RSNP Descending (as tie-breaker)
        ind_ranked = ind_ranked.sort_values(['group_score', 'rsnp'], ascending=[False, False])
        
        # 5. RSI Entry Filter & Selection
        if self.rsi_threshold > 0 and not self.rsi_cache.empty:
             valid_cache = [d for d in self.rsi_cache.index if d <= actual_calc_date]
             if valid_cache:
                 rsi_date = max(valid_cache)
                 univ_isins = universe['isin'].tolist()
                 valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
                 if valid_isins:
                     rsis = self.rsi_cache.loc[rsi_date, valid_isins]
                     passed = rsis[rsis > self.rsi_threshold].index.tolist()
                     universe = universe[universe['isin'].isin(passed)]
        
        if universe.empty: return {}

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
        
        num_final = len(selected_isins)
        if num_final >= self.num_stocks:
            w = 1.0 / num_final
        else:
            w = max(0.0667, 1.0 / num_final) if num_final > 0 else 0
            w = min(0.10, w)
            
        return {isin: w for isin in selected_isins}

def run_group_sort_variation():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
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

    print("Running Group Score Sorting Variation...")
    warnings.filterwarnings('ignore')

    strat = GroupSortStrategy(dh, num_stocks=15, 
                              industry_group_top_pct=0.50,
                              industry_decrease_min_pct=0.50)
                                    
    port = Portfolio(10000000)
    eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    nav_df = pd.DataFrame(port.nav_history)
    output_path = repo_root / "outputs/group_sort_nav.csv"
    nav_df.to_csv(output_path, index=False)
    
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("GROUP SCORE SORT VARIATION PERFORMANCE")
    print("="*60)
    print(f"{'Absolute Return':<20} : {stats['Absolute Return']}")
    print(f"{'CAGR':<20} : {stats['CAGR']}")
    print(f"{'Max Drawdown':<20} : {stats['Max Drawdown']}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']}")
    print("\n")
    
    # Comparison
    print("="*60)
    print("COMPARISON VS CHAMPION BASELINE")
    print("="*60)
    print(f"{'Metric':<20} | {'Group Sort':>15} | {'Champion':>15}")
    print("-" * 55)
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'22.54%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-41.09%':>15}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']:>15} | {'0.85':>15}")
    print("="*60)

    # Plot
    import matplotlib.pyplot as plt
    baseline_path = repo_root / "outputs/final_champion_nav.csv"
    if baseline_path.exists():
        champ_nav = pd.read_csv(baseline_path)
        champ_nav['date'] = pd.to_datetime(champ_nav['date'])
        champ_nav = champ_nav.set_index('date')['nav']
        var_nav = nav_df.set_index('date')['nav']
        plt.figure(figsize=(12, 6))
        plt.plot(champ_nav, label='Champion (RSNP Sort)', alpha=0.7)
        plt.plot(var_nav, label='Variation (Group Score Sort)', linewidth=2)
        plt.title('Strategy Comparison: Ranking Methodology')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(repo_root / "outputs/group_sort_comparison.png")
        print(f"Chart saved to: {repo_root / 'outputs/group_sort_comparison.png'}")

if __name__ == "__main__":
    run_group_sort_variation()
