#!/usr/bin/env python
from pathlib import Path
import sys
import pandas as pd

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_momentum.base_momentum import BaseIndustryMomentum

class IM_Top1000_Large_RS(BaseIndustryMomentum):
    def __init__(self):
        super().__init__()
        self.UNIVERSE_SIZE = 1000
        self.MC_SORT_ASCENDING = False
        
        # Load Top 1000 Benchmark
        bench_file = self.base_path / 'analysis/outputs/benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-02-09.csv'
        self.universe_bench = pd.read_csv(bench_file)
        self.universe_bench['date'] = pd.to_datetime(self.universe_bench['date'])
        self.universe_bench = self.universe_bench.sort_values('date')

    def calculate_selection(self, date):
        # 1. UNIVERSE
        p_slice = self.price_df[(self.price_df['date'] <= date) & (self.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
        p_slice['mc'] = p_slice['close'] * p_slice['isin'].map(self.shares_map)
        universe_isins = p_slice.dropna(subset=['mc']).sort_values('mc', ascending=False).head(self.UNIVERSE_SIZE)['isin'].tolist()
        liquid_isins = universe_isins

        # 2. RS RANKING (AVERAGE RETURN VS BENCHMARK)
        rs_date = date - pd.Timedelta(days=self.LAG_DAYS)
        
        # Universe Bench Ret
        end_bench = self.universe_bench[self.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
        start_date_bench = rs_date - pd.Timedelta(days=self.RS_LOOKBACK_DAYS)
        start_bench = self.universe_bench[self.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
        univ_bench_ret = (end_bench / start_bench) - 1

        all_industries = self.industry_df['industry'].unique()
        rs_results = []
        for ind in all_industries:
            ind_ret = self.get_industry_ret(ind, rs_date, self.RS_LOOKBACK_DAYS)
            rs = ind_ret - univ_bench_ret
            rs_results.append({'industry': ind, 'rs': rs})
        
        rs_df = pd.DataFrame(rs_results)
        ranked_inds = rs_df.sort_values('rs', ascending=False)['industry'].tolist()
        
        # 3. STOCK SELECTION
        selected = []
        for ind in ranked_inds:
            ind_isins = self.industry_df[self.industry_df['industry'] == ind]['isin'].tolist()
            ind_candidates = [isin for isin in ind_isins if isin in liquid_isins]
            ind_pool = p_slice[p_slice['isin'].isin(ind_candidates)].sort_values('mc', ascending=self.MC_SORT_ASCENDING)
            pick = ind_pool.head(4)['isin'].tolist()
            for isin in pick:
                if len(selected) < self.NUM_STOCKS:
                    selected.append(isin)
                else: break
            if len(selected) >= self.NUM_STOCKS: break
        return selected

if __name__ == "__main__":
    IM_Top1000_Large_RS().run()
