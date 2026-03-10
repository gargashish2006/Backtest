import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class StructuralAlphaGroupStrategy:
    """
    Hierarchical Structural Alpha Strategy:
    1. Rank Industry Groups by cleaning breadth (Top 50%).
    2. Rank Industries within those Top Groups by breadth.
    3. Select Top 3 Stocks per Industry by Market Cap.
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 30,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 shareholder_lookback_quarters: int = 8,
                 max_weight_per_stock: float = 0.10,
                 group_top_pct: float = 0.50,
                 group_filter_mode: str = 'top',
                 industry_absolute_threshold: float = 0.0):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        self.max_weight_per_stock = max_weight_per_stock
        self.group_top_pct = group_top_pct
        self.group_filter_mode = group_filter_mode
        self.industry_absolute_threshold = industry_absolute_threshold

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Hierarchical selection logic."""
        # 1-Week Lag for Signal Stability
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # 1. Shareholder Data
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, 
                                                 lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty:
            return {}
        
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        
        # 2. Hierarchical Filter
        # A. Group Breadth
        group_stats = sh_trend.groupby('group')['decreased'].mean().sort_values(ascending=(self.group_filter_mode == 'bottom'))
        num_groups = max(1, int(len(group_stats) * self.group_top_pct))
        top_groups = group_stats.head(num_groups).index.tolist()
        
        # B. Industry Breadth (Only for Top Groups + Absolute Floor)
        filtered_sh = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = filtered_sh.groupby('industry')['decreased'].mean()
        
        # Apply Absolute Threshold
        ind_stats = ind_stats[ind_stats >= self.industry_absolute_threshold].sort_values(ascending=False)
        
        # 3. Universe & Liquidity
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty:
            return {}
            
        # Add basic liquidity filter
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 4. Selection Loop
        selected = []
        for ind in ind_stats.index:
            # Filter universe for this industry
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            
            # Pick top N stocks per industry
            top_stocks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_stocks:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks:
                        break
            if len(selected) >= self.num_stocks:
                break

        if not selected:
            return {}

        # 5. Equal Weighting
        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}
