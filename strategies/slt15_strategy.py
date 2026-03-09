import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class SLT15Strategy:
    """
    SLT15 Strategy (Staggered Long Term 15):
    - Top 35% Industry Group Breadth Filter
    - Top 35% Industry Breadth Filter (within top groups)
    - Top 1000 Market Cap Universe
    - Rank by Individual Shareholder Count Change % (8Q Lookback, Most negative first)
    - Select Top 5 Industries, Max 3 Stocks per Industry
    - Equal Industry Weight (20% per sector)
    - Quarterly Rebalance, 2-Year Holding Period
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
        """Calculates SLT15 selection and weights for a given date."""
        top_industries_breadth = self.get_qualified_industries(date)
        if not top_industries_breadth: return {}

        # Get SH trend again for ranking (could be optimized but keeping it simple for now)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.lookback_quarters)
        
        # Filter for qualified pool
        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in self.dh.isin_to_industry and self.dh.isin_to_industry[isin] in top_industries_breadth:
                stocks_info.append({
                    'isin': isin,
                    'industry': self.dh.isin_to_industry[isin],
                    'sh_change_pct': (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                })
        
        if not stocks_info: return {}
        qualified_df = pd.DataFrame(stocks_info)
        
        # Market Cap (Top 1000)
        univ = self.dh.get_universe(date, size=self.universe_size)
        if univ.empty:
            return {}
        univ_isins = set(univ['isin'].tolist())
        final_pool = qualified_df[qualified_df['isin'].isin(univ_isins)].copy()

        if final_pool.empty:
            return {}

        # 2. SLT15 Basket Selection
        # Rank by SH-Change % (Max decrease first)
        sorted_pool = final_pool.sort_values('sh_change_pct', ascending=True)

        selected_industries = []
        industry_to_isins = {}

        for _, row in sorted_pool.iterrows():
            ind = row['industry']
            isin = row['isin']
            if ind not in selected_industries:
                if len(selected_industries) < self.num_industries:
                    selected_industries.append(ind)
                    industry_to_isins[ind] = [isin]
            else:
                if len(industry_to_isins[ind]) < self.max_per_industry:
                    industry_to_isins[ind].append(isin)

        if not selected_industries:
            return {}

        # 3. Weighting Logic (Equal Industry Wise)
        total_n = len(selected_industries)
        ind_weight = 1.0 / total_n
        selection_with_weights = {}
        for ind in selected_industries:
            isins = industry_to_isins[ind]
            stock_weight = ind_weight / len(isins)
            for isin in isins:
                selection_with_weights[isin] = stock_weight

        return selection_with_weights
