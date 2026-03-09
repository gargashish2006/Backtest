
import pandas as pd
import numpy as np
from typing import Dict, List
from data.data_handler import DataHandler

class StaticStrategyV2:
    def __init__(self, data_handler: DataHandler):
        self.dh = data_handler
        
        # Load Nifty 500 Benchmark (Similar logic to ML, but cleaner)
        repo_root = self.dh.price_path.parent.parent
        bench_path = repo_root / "benchmarks/Nifty_500/timeseries.parquet"
        if not bench_path.exists():
             bench_path = repo_root / "benchmarks/Nifty_500/timeseries.csv"
             
        if bench_path.exists():
            if bench_path.suffix == '.parquet':
                self.bench_df = pd.read_parquet(bench_path)
            else:
                self.bench_df = pd.read_csv(bench_path)
            self.bench_df['date'] = pd.to_datetime(self.bench_df['date'])
            # Standardize column
            if 'index_value' in self.bench_df.columns:
                 self.bench_series = self.bench_df.set_index('date')['index_value'].sort_index()
            elif 'close' in self.bench_df.columns:
                 self.bench_series = self.bench_df.set_index('date')['close'].sort_index()
            elif 'nav' in self.bench_df.columns:
                 self.bench_series = self.bench_df.set_index('date')['nav'].sort_index()
        else:
            print("Warning: Nifty 500 not found for Static V2. Using Top 1000 Bench as proxy.")
            if 'index_value' in self.dh.top_1000_bench.columns:
                 self.bench_series = self.dh.top_1000_bench.set_index('date')['index_value'].sort_index()
            else:
                 self.bench_series = self.dh.top_1000_bench.set_index('date')['cumulative_return'].sort_index()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Calculation dates
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= date])
        
        # 2. Universe: Top 1000 Liquid
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        isins = universe['isin'].tolist()
        
        # 3. Generate Features
        
        # --- Shareholder Decrease ---
        trend_4q = self.dh.get_shareholder_trend(actual_calc_date, lookback_quarters=4)
        map_4q = dict(zip(trend_4q['isin'], trend_4q['decreased'].astype(int))) if not trend_4q.empty else {}
        
        # --- RSNP ---
        b_curr = self.bench_series.asof(actual_calc_date)
        if pd.isna(b_curr): return {}
        
        date_1y = actual_calc_date - pd.DateOffset(years=1)
        b_1y = self.bench_series.asof(date_1y)
        if pd.isna(b_1y): return {}
        
        # Find nearest trading dates for lookbacks
        def get_nearest_date(target):
            valid_dates = [d for d in all_dates if d <= target]
            return max(valid_dates) if valid_dates else None
        
        d_1y_valid = get_nearest_date(date_1y)
        prices_curr = self.dh.get_daily_prices(actual_calc_date)
        prices_1y = self.dh.get_daily_prices(d_1y_valid) if d_1y_valid else {}
        
        # --- Static V2: Enrich Universe ---
        u_df = universe[['isin', 'mc']].copy()
        u_df['ind'] = u_df['isin'].map(self.dh.isin_to_industry).fillna('Unknown')
        u_df['group'] = u_df['isin'].map(self.dh.isin_to_group).fillna('Unknown')
        
        u_df['sh_dec_4q'] = u_df['isin'].map(map_4q).fillna(0)
        
        rsnp_vals = []
        for isin in u_df['isin']:
            p_c = prices_curr.get(isin)
            p_1y = prices_1y.get(isin)
            if p_c and p_1y:
                ratio_c = p_c / b_curr
                ratio_1y = p_1y / b_1y
                rsnp = (ratio_c / ratio_1y) - 1
            else:
                rsnp = np.nan
            rsnp_vals.append(rsnp)
        
        u_df['rsnp_1y'] = rsnp_vals
        
        # Compute Industry/Group Momentum (Static Logic Step)
        # We define "Group Momentum" as Mean RSNP of the group
        grp_mom = u_df.groupby('group')['rsnp_1y'].mean()
        ind_mom = u_df.groupby('ind')['rsnp_1y'].mean()
        
        map_grp_mom = grp_mom.to_dict()
        map_ind_mom = ind_mom.to_dict()
        
        u_df['grp_mom_1y'] = u_df['group'].map(map_grp_mom)
        u_df['ind_mom_1y'] = u_df['ind'].map(map_ind_mom)
        
        # --- STATIC RULES (Removing Non-Linear ML) ---
        
        # Rule 1: Must be Contrarian (Shareholder Decrease 4Q)
        filtered = u_df[u_df['sh_dec_4q'] == 1].copy()
        
        # Rule 2: Stock Momentum (RSNP 1Y > 0.4) - The Classic Champion Filter
        filtered = filtered[filtered['rsnp_1y'] > 0.4]
        
        # Rule 3: Industry Confirmation (New V2 Logic)
        # Instead of chasing the *hottest* group (like ML did), we just filter out *dying* groups.
        # Rule: Only buy if Industry OR Group Momentum is POSITIVE (> 0).
        # This prevents buying a "strong stock in a weak sector" (false breakout).
        filtered = filtered[ (filtered['grp_mom_1y'] > 0) | (filtered['ind_mom_1y'] > 0) ]
        
        # Selection Logic
        # Rank by Stock RSNP (Standard Momentum)
        if filtered.empty: return {}
        
        filtered = filtered.sort_values('rsnp_1y', ascending=False)
        top_n = filtered.head(20)['isin'].tolist()
        
        if not top_n: return {}
        
        w = 1.0 / len(top_n)
        return {isin: w for isin in top_n}
