
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
warnings.filterwarnings('ignore')

class DiagnosticQtlyStrategy(ContrarianBreadthStrategy):
    def __init__(self, data_handler, num_stocks=15, 
                 industry_group_top_pct=0.50, 
                 industry_decrease_min_pct=0.35):
        super().__init__(data_handler, num_stocks)
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        
    def get_details(self, date):
        # Implementation of Quarterly Count selection logic, but returning the dataframe
        calc_date = pd.Timestamp(date)
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])

        metrics = self.dh.get_daily_metrics(actual_calc_date)
        universe = metrics.sort_values('mc', ascending=False).head(self.universe_size)
        
        # Shareholder Logic
        sh_data = self.dh.shareholding_df.copy()
        if 'date' not in sh_data.columns:
             sh_data['date'] = pd.to_datetime(sh_data['quarter'])
        
        valid_sh = sh_data[sh_data['date'] <= calc_date].copy()
        univ_isins = universe['isin'].tolist()
        valid_sh = valid_sh[valid_sh['isin'].isin(univ_isins)]
        valid_sh = valid_sh.sort_values(['isin', 'date'], ascending=[True, False])
        recent_sh = valid_sh.groupby('isin').head(5)
        recent_sh['prev_sh_held'] = recent_sh.groupby('isin')['total_shareholders'].shift(-1)
        recent_sh['is_decrease'] = recent_sh['total_shareholders'] < recent_sh['prev_sh_held']
        changes = recent_sh.dropna(subset=['prev_sh_held'])
        
        isin_score = changes.groupby('isin')['is_decrease'].sum().reset_index()
        isin_score.columns = ['isin', 'decrease_count']
        isin_score['group'] = isin_score['isin'].map(self.dh.isin_to_group)
        isin_score['industry'] = isin_score['isin'].map(self.dh.isin_to_industry)
        
        # Group Score
        group_stats = isin_score.groupby('group')['decrease_count'].agg(['sum', 'count']).reset_index()
        group_stats['max_possible'] = group_stats['count'] * 4
        group_stats['group_score_pct'] = group_stats['sum'] / group_stats['max_possible']
        
        num_to_pick = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.sort_values('group_score_pct', ascending=False).head(num_to_pick)['group'].tolist()
        
        # Industry Score
        ind_in_groups = isin_score[isin_score['group'].isin(top_groups)]
        ind_stats = ind_in_groups.groupby('industry')['decrease_count'].agg(['sum', 'count']).reset_index()
        ind_stats['max_possible'] = ind_stats['count'] * 4
        ind_stats['ind_score_pct'] = ind_stats['sum'] / ind_stats['max_possible']
        
        # Map back the Group Score for visibility
        group_map = group_stats.set_index('group')['group_score_pct'].to_dict()
        ind_stats['group_name'] = ind_stats['industry'].map(lambda x: isin_score[isin_score['industry']==x]['group'].iloc[0])
        ind_stats['group_score'] = ind_stats['group_name'].map(group_map)
        
        # Filter Industries
        qualified_industries = ind_stats[ind_stats['ind_score_pct'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return pd.DataFrame()
        
        # RSNP
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1

        def get_prices_map(target_date):
            window = [d for d in all_dates if d <= target_date][-30:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_prices_map(actual_calc_date)
        p_start_map = get_prices_map(actual_lookback_start)

        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins, eligible = 0, 0
            for isin in ind_isins:
                p1, p0 = p_end_map.get(isin), p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})

        ind_ranked = pd.DataFrame(industry_rsnp)
        
        # Join with ind_stats for the final table
        final_table = pd.merge(ind_ranked, ind_stats, on='industry')
        final_table = final_table.sort_values('rsnp', ascending=False).reset_index(drop=True)
        final_table['rank'] = final_table.index + 1
        
        return final_table[['rank', 'industry', 'group_name', 'group_score', 'ind_score_pct', 'rsnp']]

def run():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Find the rebalance date in Feb 2026
    all_dates = dh.get_all_dates()
    target_date = pd.Timestamp("2026-02-15")
    actual_reb_date = max([d for d in all_dates if d <= target_date])
    
    print(f"Extracting details for Rebalance Date: {actual_reb_date}")
    
    strat = DiagnosticQtlyStrategy(dh)
    details = strat.get_details(actual_reb_date)
    
    if details.empty:
        print("No qualified industries found.")
    else:
        print("\nTOP INDUSTRIES - FEB 2026 (QTLY COUNT 50%/35% COMBO)")
        print("="*100)
        # Format percentages
        details['group_score'] = details['group_score'].map(lambda x: f"{x:.1%}")
        details['ind_score_pct'] = details['ind_score_pct'].map(lambda x: f"{x:.1%}")
        details['rsnp'] = details['rsnp'].map(lambda x: f"{x:.2f}")
        
        print(details.to_string(index=False))
        print("="*100)

if __name__ == "__main__":
    run()
