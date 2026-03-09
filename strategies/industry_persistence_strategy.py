import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class IndustryPersistenceStrategy:
    """
    Industry Persistence Strategy (Sticky Structural):
    - 12-Quarter (3Y) Shareholder Decrease Breadth at Industry Level.
    - Rank Industries by Cleaning Breadth (High to Low).
    - Select Top 15 Industries.
    - Select 1 Stock per Industry (Largest by Market Cap on Entry).
    - Sticky Logic: Keep the same stock as long as its Industry stays in the Top 15.
    - Replace only stocks whose industries drop out of the Top 15.
    - Equal Weight allocation.
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_industries: int = 15,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 shareholder_lookback_quarters: int = 12):
        self.dh = data_handler
        self.num_industries = num_industries
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        
        # Internal State: industry -> isin
        self.current_assignments: Dict[str, str] = {}

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Selection logic with Industry Persistence."""
        # 1-Week Lag for Signal Stability
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # 1. Rank Industries (12Q SH Breadth)
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, 
                                                 lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty:
            return {}
        
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        ind_stats = sh_trend.groupby('industry')['decreased'].mean().reset_index()
        top_15_industries = ind_stats.sort_values('decreased', ascending=False).head(self.num_industries)['industry'].tolist()

        # 2. Get Universe & Liquidity (for potential new entries)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        
        # Add liquidity filter
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 3. Handle Persistence Logic
        new_assignments = {}
        
        for industry in top_15_industries:
            # If we already have a stock for this industry, keep it
            if industry in self.current_assignments:
                isin = self.current_assignments[industry]
                # Optional: Check if stock still exists/is liquid. 
                # For this strategy, we assume stickiness unless the industry itself fails.
                new_assignments[industry] = isin
            else:
                # NEW Industry entering the Top 15: Pick the largest stock
                ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == industry].sort_values('mc', ascending=False)
                if not ind_stocks.empty:
                    new_isin = ind_stocks.iloc[0]['isin']
                    new_assignments[industry] = new_isin
        
        # Update State
        self.current_assignments = new_assignments
        
        # 4. Generate Weight Map (Equal Weight)
        if not new_assignments:
            return {}
            
        final_isins = list(new_assignments.values())
        weight = 1.0 / len(final_isins)
        
        return {isin: weight for isin in final_isins}
