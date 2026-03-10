import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class SLT15IndustryMedianRankStrategy:
    """
    SLT15 Variation:
    - Top 35% Industry Group Breadth Filter
    - Top 35% Industry Breadth Filter (within top groups)
    - Top 1000 Market Cap Universe
    - Rank selected Industries by the MEDIAN SH Decrease of their stocks
    - Within those Top 5 Industries, select Max 3 Stocks with lowest absolute SH change
    - Equal Industry Weight (20% per sector)
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_industries: int = 5,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 lookback_quarters: int = 8):
        self.dh = data_handler
        self.num_industries = num_industries
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.lookback_quarters = lookback_quarters

    def get_qualified_industries(self, date: pd.Timestamp) -> List[str]:
        """Returns the list of industries passing the 35/35 breadth filter."""
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.lookback_quarters)
        if sh_trend.empty: return []

        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in self.dh.isin_to_group and isin in self.dh.isin_to_industry:
                stocks_info.append({
                    'isin': isin,
                    'group': self.dh.isin_to_group[isin],
                    'industry': self.dh.isin_to_industry[isin],
                    'decreased': row['decreased']
                })
        
        if not stocks_info: return []
        df_info = pd.DataFrame(stocks_info)

        group_stats = df_info.groupby('group')['decreased'].mean()
        top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35))).index.tolist()

        rel_df = df_info[df_info['group'].isin(top_groups)]
        ind_stats = rel_df.groupby('industry')['decreased'].mean()
        return ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Calculates selection using Industry Median SH Decrease ranking."""
        top_industries_breadth = self.get_qualified_industries(date)
        if not top_industries_breadth: return {}

        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.lookback_quarters)
        univ = self.dh.get_universe(date, size=self.universe_size)
        if univ.empty or sh_trend.empty: return {}
        univ_isins = set(univ['isin'].tolist())
        
        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in univ_isins and isin in self.dh.isin_to_industry:
                ind = self.dh.isin_to_industry[isin]
                if ind in top_industries_breadth:
                    stocks_info.append({
                        'isin': isin,
                        'industry': ind,
                        'sh_change_pct': (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                    })
        
        if not stocks_info: return {}
        qualified_df = pd.DataFrame(stocks_info)
        
        # Calculate Median SH Decrease per industry
        # sh_change_pct is negative for a decrease, so the lower the value, the higher the decrease.
        # We want to rank by Most Negative Median (Ascending order of median)
        ind_median = qualified_df.groupby('industry')['sh_change_pct'].median()
        sorted_industries = ind_median.sort_values(ascending=True).index.tolist()
        
        # Pick top 5 industries
        top_selected_industries = sorted_industries[:self.num_industries]

        # Pick lowest SH change stocks within selected industries
        selection_with_weights = {}
        ind_weight = 1.0 / len(top_selected_industries)
        
        for ind in top_selected_industries:
            ind_stocks = qualified_df[qualified_df['industry'] == ind]
            if ind_stocks.empty: continue
            
            top_stocks = ind_stocks.sort_values('sh_change_pct', ascending=True).head(self.max_per_industry)
            stock_weight = ind_weight / len(top_stocks)
            
            for _, row in top_stocks.iterrows():
                selection_with_weights[row['isin']] = stock_weight

        return selection_with_weights
