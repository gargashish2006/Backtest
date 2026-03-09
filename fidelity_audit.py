
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from research_quarterly_count import OptimizedQuarterlyCountStrategy, precompute_data
import warnings
warnings.filterwarnings('ignore')

class OriginalQuarterlyCountStrategy(ContrarianBreadthStrategy):
    def __init__(self, dh, num_stocks=15):
        super().__init__(dh, num_stocks)
        self.industry_group_top_pct = 0.50
        self.industry_decrease_min_pct = 0.35
        self.max_per_industry = 4
        self.rsi_threshold = 50

    def calculate_selection(self, date: pd.Timestamp):
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date-pd.Timedelta(days=365))])
        
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        universe = metrics.sort_values('mc', ascending=False).head(500)
        
        # Liquidity (0.005% from strategy or 0.01%?)
        # Let's use 0.0001 (0.01%) to match what I put in optimized
        rolling_start = actual_calc_date - pd.Timedelta(days=40)
        liq_window = [d for d in all_dates if rolling_start <= d <= actual_calc_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liq_window)]
        avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * 0.0001)]
        
        # Shareholder Logic
        sh_data = self.dh.shareholding_df.copy()
        sh_data['date'] = pd.to_datetime(sh_data['quarter'], errors='coerce')
        valid_sh = sh_data[sh_data['date'] <= actual_calc_date].sort_values(['isin', 'date'], ascending=[True, False])
        valid_sh = valid_sh[valid_sh['isin'].isin(universe['isin'].tolist())]
        recent_sh = valid_sh.groupby('isin').head(5)
        recent_sh['prev_sh_held'] = recent_sh.groupby('isin')['total_shareholders'].shift(-1)
        recent_sh['is_decrease'] = recent_sh['total_shareholders'] < recent_sh['prev_sh_held']
        isin_score = recent_sh.dropna(subset=['prev_sh_held']).groupby('isin')['is_decrease'].sum().reset_index()
        isin_score.columns = ['isin', 'decrease_count']
        isin_score['group'] = isin_score['isin'].map(self.dh.isin_to_group)
        isin_score['industry'] = isin_score['isin'].map(self.dh.isin_to_industry)
        
        group_stats = isin_score.groupby('group')['decrease_count'].agg(['sum', 'count']).reset_index()
        group_stats['score_pct'] = group_stats['sum'] / (group_stats['count'] * 4)
        top_groups = group_stats[group_stats['count']>=5].sort_values('score_pct', ascending=False).head(int(len(group_stats)*0.5))['group'].tolist()
        
        ind_in_groups = isin_score[isin_score['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decrease_count'].agg(['sum', 'count']).reset_index()
        ind_stats['score_pct'] = ind_stats['sum'] / (ind_stats['count'] * 4)
        qualified_industries = ind_stats[ind_stats['score_pct'] >= 0.35]['industry'].tolist()
        
        # Diagnostics
        print(f"\nAUDIT: {date.date()}")
        print(f"Top 3 Groups: {top_groups[:3]}")
        print(f"Qualified Industries: {len(qualified_industries)}")
        
        # RSNP
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()
        p1_map, p0_map = get_map(actual_calc_date), get_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]
            wins, total = 0, 0
            for i in ind_isins:
                p1, p0 = p1_map.get(i), p0_map.get(i)
                if p1 and p0 and p0 > 0:
                    total += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if total > 0: industry_rsnp.append({'industry': ind, 'rsnp': wins/total})
        
        ind_ranked = pd.DataFrame(industry_rsnp).sort_values('rsnp', ascending=False)
        
        # Selection
        rsi_cache = self.dh.get_weekly_rsi_cache()
        rsi_date = max([d for d in rsi_cache.index if d <= actual_calc_date])
        rsis = rsi_cache.loc[rsi_date]
        passed = [i for i in universe['isin'] if rsis.get(i, 0) > 50]
        
        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = [i for i in passed if self.dh.isin_to_industry.get(i) == ind]
            for i in ind_stocks[:4]:
                if i not in selected: 
                    selected.append(i)
                    if len(selected) >= 15: break
            if len(selected) >= 15: break
        return selected, group_stats.sort_values('score_pct', ascending=False).head(20), ind_ranked

def run_fidelty_test():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    test_date = pd.Timestamp("2024-02-15")
    
    print("\nRUNNING ORIGINAL...")
    orig = OriginalQuarterlyCountStrategy(dh)
    sel_orig, groups_orig, rsnp_orig = orig.calculate_selection(test_date)
    
    print("\nRUNNING OPTIMIZED...")
    cache = precompute_data(dh, [test_date])
    opt = OptimizedQuarterlyCountStrategy(dh, cache, num_stocks=15, 
                                         industry_group_top_pct=0.50,
                                         industry_decrease_min_pct=0.35)
    
    # Extract optimized group stats for audit
    cache_entry = cache[test_date]
    isin_scores = cache_entry['isin_scores']
    g_stats = isin_scores.groupby('group')['decrease_count'].agg(['sum', 'count']).reset_index()
    g_stats['score_pct'] = g_stats['sum'] / (g_stats['count'] * 4)
    groups_opt = g_stats.sort_values('score_pct', ascending=False).head(20)
    
    print(f"Optimized Top 10 Groups:\n{groups_opt.head(10)[['group', 'score_pct']].to_string(index=False)}")

    # Extract optimized RSNP data for audit
    ind_rsnp_map = cache_entry['ind_rsnp_map']
    rsnp_opt_df = pd.DataFrame(list(ind_rsnp_map.items()), columns=['industry', 'rsnp']).sort_values('rsnp', ascending=False)
    print(f"Optimized Top 10 Industries (All industries):\n{rsnp_opt_df.head(10).to_string(index=False)}")
    
    sel_opt_weights = opt.calculate_selection(test_date)
    sel_opt = list(sel_opt_weights.keys())
    
    print("\nRESULTS:")
    print(f"Original: {len(sel_orig)} stocks")
    print(f"Optimized: {len(sel_opt)} stocks")
    common = set(sel_orig).intersection(set(sel_opt))
    print(f"Common: {len(common)}")
    if len(common) < len(sel_orig):
        print(f"Only in Original: {set(sel_orig) - set(sel_opt)}")
        print(f"Only in Optimized: {set(sel_opt) - set(sel_orig)}")

if __name__ == "__main__":
    run_fidelty_test()
