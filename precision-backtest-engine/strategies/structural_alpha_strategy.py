import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class StructuralAlphaStrategy:
    """
    Structural Alpha Strategy (Long-Term):
    - 12-Quarter (3Y) Shareholder Decrease Breadth at Industry Level.
    - Rank Industries by Cleaning Breadth (High to Low).
    - Select Top 3 Stocks per Industry by Market Cap (High to Low).
    - Standard Top 1000 Universe & Liquidity (0.005%) Filters.
    - Portfolio size governed by number of qualified industries.
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 shareholder_lookback_quarters: int = 12,
                 max_weight_per_stock: float = 0.10):
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        self.max_weight_per_stock = max_weight_per_stock

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Selection logic for Structural Alpha."""
        # 1-Week Lag for Signal Stability
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # 1. Shareholder Filters (12Q Lookback)
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, 
                                                 lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty:
            return {}
        
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # Calculate Industry Breadth (Percentage of stocks cleaning)
        ind_stats = sh_trend.groupby('industry')['decreased'].mean().reset_index()
        # Rank all industries by cleaning breadth
        ind_ranked = ind_stats.sort_values('decreased', ascending=False)

        # 2. Universe & Liquidity (Signal Date)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty:
            return {}
            
        # Add basic liquidity filter (Median traded value vs MC)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 3. Selection Loop
        selected = []
        # Traverse industries in ranked order
        for _, row in ind_ranked.iterrows():
            ind = row['industry']
            # Filter universe for this industry and sort by MC (High to Low)
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

        # 4. Equal Weighting with Caps
        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}
