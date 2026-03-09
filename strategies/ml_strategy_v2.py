
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List
from data.data_handler import DataHandler

class MLStrategyV2:
    def __init__(self, data_handler: DataHandler, model_path: Path):
        self.dh = data_handler
        print(f"Loading ML V2 Model from {model_path}...")
        self.model = joblib.load(model_path)
        
        # Load Nifty 500 Benchmark for RSNP calculation
        # Same logic as training: try to load time series
        repo_root = model_path.parent.parent
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
            print("Warning: Nifty 500 not found for ML Strategy. Using Top 1000 Bench as proxy.")
            if 'index_value' in self.dh.top_1000_bench.columns:
                 self.bench_series = self.dh.top_1000_bench.set_index('date')['index_value'].sort_index()
            else:
                 self.bench_series = self.dh.top_1000_bench.set_index('date')['cumulative_return'].sort_index()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Calculation dates
        
        # In training, we calculated features at the rebalance date.
        # But `dh.get_daily_metrics(date)` might not have data if it's a holiday.
        # Better to find latest trading date <= date.
        
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= date])
        
        # 2. Universe: Top 1000 Liquid
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        isins = universe['isin'].tolist()
        
        # 3. Generate Features (Point-in-Time)
        # We need to construct a DataFrame with columns: 
        # ['sh_decrease_4q_binary', 'sh_decrease_6q_binary', 'sh_decrease_8q_binary', 
        #  'rsnp_6m', 'rsnp_1y', 'rsnp_2y',
        #  'ind_sh_breadth', 'grp_sh_breadth', 'ind_rsnp_1y', 'grp_rsnp_1y']
        
        # --- Shareholder Decrease ---
        trend_4q = self.dh.get_shareholder_trend(actual_calc_date, lookback_quarters=4)
        trend_6q = self.dh.get_shareholder_trend(actual_calc_date, lookback_quarters=6)
        trend_8q = self.dh.get_shareholder_trend(actual_calc_date, lookback_quarters=8)
        
        map_4q = dict(zip(trend_4q['isin'], trend_4q['decreased'].astype(int))) if not trend_4q.empty else {}
        map_6q = dict(zip(trend_6q['isin'], trend_6q['decreased'].astype(int))) if not trend_6q.empty else {}
        map_8q = dict(zip(trend_8q['isin'], trend_8q['decreased'].astype(int))) if not trend_8q.empty else {}
        
        # --- RSNP ---
        # Cache benchmark series for this date
        b_curr = self.bench_series.asof(actual_calc_date)
        
        if pd.isna(b_curr): return {}
        
        date_6m = actual_calc_date - pd.DateOffset(months=6)
        date_1y = actual_calc_date - pd.DateOffset(years=1)
        date_2y = actual_calc_date - pd.DateOffset(years=2)
        
        b_6m = self.bench_series.asof(date_6m)
        b_1y = self.bench_series.asof(date_1y)
        b_2y = self.bench_series.asof(date_2y)
        
        # If benchmark history missing, can't calculate RSNP
        if pd.isna(b_6m) or pd.isna(b_1y) or pd.isna(b_2y): return {}
        
        # Pre-fetch prices for universe
        prices_curr = self.dh.get_daily_prices(actual_calc_date)
        
        # Find nearest trading dates for lookbacks
        def get_nearest_date(target):
            valid_dates = [d for d in all_dates if d <= target]
            return max(valid_dates) if valid_dates else None
            
        d_6m_valid = get_nearest_date(date_6m)
        d_1y_valid = get_nearest_date(date_1y)
        d_2y_valid = get_nearest_date(date_2y)
        
        prices_6m = self.dh.get_daily_prices(d_6m_valid) if d_6m_valid else {}
        prices_1y = self.dh.get_daily_prices(d_1y_valid) if d_1y_valid else {}
        prices_2y = self.dh.get_daily_prices(d_2y_valid) if d_2y_valid else {}
        
        # --- V2 Step: Enrich Universe for aggregation ---
        u_df = universe[['isin']].copy()
        
        # Map Industry/Group manually
        u_df['ind'] = u_df['isin'].map(self.dh.isin_to_industry).fillna('Unknown')
        u_df['group'] = u_df['isin'].map(self.dh.isin_to_group).fillna('Unknown')
        
        # Calculate individual features for ALL universe stocks
        # We need this to compute aggregates
        
        # Map Shareholder Decrease (4Q)
        u_df['sh_dec_4q'] = u_df['isin'].map(map_4q).fillna(0)
        
        # Map RSNP 1Y
        # We need to compute it manually row by row or vectorized?
        # Vectorized over dicts is okay for 1000 items
        
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
        
        # Drop NaNs before aggregation? Or keep as NaN?
        # Groupby ignores NaNs
        
        # Compute Aggregates
        ind_breadth = u_df.groupby('ind')['sh_dec_4q'].mean()
        grp_breadth = u_df.groupby('group')['sh_dec_4q'].mean()
        
        ind_mom = u_df.groupby('ind')['rsnp_1y'].mean()
        grp_mom = u_df.groupby('group')['rsnp_1y'].mean()
        
        # Create Mapping Dicts
        map_ind_breadth = ind_breadth.to_dict()
        map_grp_breadth = grp_breadth.to_dict()
        map_ind_mom = ind_mom.to_dict()
        map_grp_mom = grp_mom.to_dict()
        
        # --- Build Feature Vector ---
        features_list = []
        valid_isins = []
        
        for idx, row in u_df.iterrows():
            isin = row['isin']
            stock_ind = row['ind']
            stock_grp = row['group']
            
            # Check full RSNP history (6M, 1Y, 2Y)
            p_c = prices_curr.get(isin)
            p_6m = prices_6m.get(isin)
            p_1y = prices_1y.get(isin)
            p_2y = prices_2y.get(isin)
            
            if not (p_c and p_6m and p_1y and p_2y): continue
            
            # Recalculate strict values (we calculated 1Y for aggregate, do it for all here)
            ratio_c = p_c / b_curr
            ratio_6m = p_6m / b_6m
            ratio_1y = p_1y / b_1y
            ratio_2y = p_2y / b_2y
            
            rsnp_6m = (ratio_c / ratio_6m) - 1
            rsnp_1y = (ratio_c / ratio_1y) - 1
            rsnp_2y = (ratio_c / ratio_2y) - 1
            
            feature_row = {
                'sh_decrease_4q_binary': map_4q.get(isin, 0),
                'sh_decrease_6q_binary': map_6q.get(isin, 0),
                'sh_decrease_8q_binary': map_8q.get(isin, 0),
                'rsnp_6m': rsnp_6m,
                'rsnp_1y': rsnp_1y,
                'rsnp_2y': rsnp_2y,
                'ind_sh_breadth': map_ind_breadth.get(stock_ind, 0),
                'grp_sh_breadth': map_grp_breadth.get(stock_grp, 0),
                'ind_rsnp_1y': map_ind_mom.get(stock_ind, 0),
                'grp_rsnp_1y': map_grp_mom.get(stock_grp, 0)
            }
            features_list.append(feature_row)
            valid_isins.append(isin)
            
        if not features_list: return {}
        
        X = pd.DataFrame(features_list)
        
        # Ensure column order matches training?
        ordered_cols = [
            'sh_decrease_4q_binary', 'sh_decrease_6q_binary', 'sh_decrease_8q_binary', 
            'rsnp_6m', 'rsnp_1y', 'rsnp_2y',
            'ind_sh_breadth', 'grp_sh_breadth', 'ind_rsnp_1y', 'grp_rsnp_1y'
        ]
        
        # Check if all cols exist
        missing = [c for c in ordered_cols if c not in X.columns]
        if missing:
            print(f"Warning: Missing columns {missing}")
            return {}
            
        X = X[ordered_cols]
        
        # 4. Predict
        scores = self.model.predict(X)
        
        # 5. Select Top N (e.g. 20)
        # Create DF with scores
        results = pd.DataFrame({'isin': valid_isins, 'score': scores})
        results = results.sort_values('score', ascending=False)
        
        # Select Top 20
        top_n = results.head(20)['isin'].tolist()
        
        if not top_n: return {}
        
        w = 1.0 / len(top_n)
        return {isin: w for isin in top_n}
