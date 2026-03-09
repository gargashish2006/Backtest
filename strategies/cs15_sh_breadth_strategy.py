"""
CS15 Shareholder Breadth Variation:
Same as CS15 but replaces the RSNP momentum filter with
12Q shareholder decrease percentage breadth as the industry ranking metric.

Changes from CS15:
- Step 3: Instead of RSNP (% stocks beating benchmark), use 12Q shareholder 
  decrease % (current quarter vs 12 quarters ago) as the industry ranking.
- Industries with higher % of stocks showing decreased shareholders rank higher.
- Threshold: >= 40% of stocks must show decreased shareholders (same cutoff as RSNP).
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from data.data_handler import DataHandler


class CS15ShBreadthStrategy:
    
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 sh_breadth_threshold: float = 0.40,
                 sh_breadth_lookback_quarters: int = 12,
                 rsi_threshold: float = 40,
                 max_weight_per_stock: float = 0.10,
                 shareholder_lookback_quarters: int = 4):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.sh_breadth_threshold = sh_breadth_threshold
        self.sh_breadth_lookback_quarters = sh_breadth_lookback_quarters
        self.rsi_threshold = rsi_threshold
        self.max_weight_per_stock = max_weight_per_stock
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        
        self.rsi_cache = pd.DataFrame()

    def precompute_rsi(self, dates: List[pd.Timestamp]):
        print("Pre-computing Weekly RSI Cache for CS15-SHB...")
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        delta = weekly_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))

    def check_exits(self, current_date: pd.Timestamp, portfolio) -> List[str]:
        if self.rsi_cache.empty: return []
        to_sell = []
        isins = list(portfolio.keys()) if isinstance(portfolio, dict) else portfolio
        valid_rsi_dates = [d for d in self.rsi_cache.index if d <= current_date]
        if not valid_rsi_dates: return []
        rsi_date = max(valid_rsi_dates)
        for isin in isins:
            if isin in self.rsi_cache.columns:
                rsi_val = self.rsi_cache.loc[rsi_date, isin]
                if pd.notna(rsi_val) and rsi_val < 39:
                    to_sell.append(isin)
        return to_sell

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1-Week Lag
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # 1. Shareholder Filters (4Q lookback for group/industry filter - same as CS15)
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # Rule 1: Group Filter (Top 50%)
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False).head(
            int(len(group_stats) * self.industry_group_top_pct))['group'].tolist()
        
        # Rule 2: Industry Filter (>= 50%)
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}

        # 3. NEW: 12Q Shareholder Decrease Breadth (replaces RSNP)
        sh_trend_12q = self.dh.get_shareholder_trend(actual_signal_date, lookback_quarters=self.sh_breadth_lookback_quarters)
        if sh_trend_12q.empty: return {}
        
        sh_trend_12q['industry'] = sh_trend_12q['isin'].map(self.dh.isin_to_industry)
        
        industry_breadth = []
        for ind in qualified_industries:
            ind_data = sh_trend_12q[sh_trend_12q['industry'] == ind]
            if len(ind_data) > 0:
                breadth = ind_data['decreased'].mean()
                industry_breadth.append({'industry': ind, 'sh_breadth': breadth})
        
        if not industry_breadth: return {}
        ind_ranked = pd.DataFrame(industry_breadth)
        
        # Filter: breadth >= threshold (40%)
        passed = ind_ranked[ind_ranked['sh_breadth'] >= self.sh_breadth_threshold].sort_values('sh_breadth', ascending=False)
        if passed.empty: return {}

        # 4. Universe & Liquidity (same as CS15)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        # 5. Weekly RSI > 40
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]
            
        if universe.empty: return {}

        # 6. Selection (Max 15, 3 per industry, rank by M-cap)
        selected = []
        for ind in passed['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_stocks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_stocks:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break
            
        if not selected: return {}
        
        # 7. Equal weight, max 10%
        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}
