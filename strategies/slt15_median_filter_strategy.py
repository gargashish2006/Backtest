import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class SLT15MedianFilterStrategy:
    """
    SLT15 Variation:
    - Top 35% Industry Group ranked by MEDIAN SH Change (most negative = highest rank)
    - Top 35% Industry ranked by MEDIAN SH Change (within top groups)
    - Top 1000 Market Cap Universe
    - Rank remaining stocks individually by SH Change
    - Select Top 5 Industries, Max 3 Stocks per Industry
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
        """Returns the list of industries passing the 35/35 median sh_change filter."""
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.lookback_quarters)
        if sh_trend.empty: return []

        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            if isin in self.dh.isin_to_group and isin in self.dh.isin_to_industry:
                sh_change = (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                stocks_info.append({
                    'isin': isin,
                    'group': self.dh.isin_to_group[isin],
                    'industry': self.dh.isin_to_industry[isin],
                    'sh_change': sh_change
                })
        
        if not stocks_info: return []
        df_info = pd.DataFrame(stocks_info)

        # Rank Groups by Median SH Change (Ascending: most negative is best)
        group_stats = df_info.groupby('group')['sh_change'].median()
        top_groups = group_stats.sort_values(ascending=True).head(max(1, int(len(group_stats) * 0.35))).index.tolist()

        # Rank Industries within Top Groups by Median SH Change
        rel_df = df_info[df_info['group'].isin(top_groups)]
        ind_stats = rel_df.groupby('industry')['sh_change'].median()
        return ind_stats.sort_values(ascending=True).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Calculates identical stock selection logic to original SLT15."""
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
        
        # Rank by SH-Change % (Max decrease first) globally
        sorted_pool = qualified_df.sort_values('sh_change_pct', ascending=True)
        
        selected_industries = []
        for ind in sorted_pool['industry']:
            if ind not in selected_industries:
                selected_industries.append(ind)
                if len(selected_industries) == self.num_industries:
                    break
        
        selection_with_weights = {}
        ind_weight = 1.0 / len(selected_industries)
        
        for ind in selected_industries:
            ind_stocks = sorted_pool[sorted_pool['industry'] == ind].head(self.max_per_industry)
            stock_weight = ind_weight / len(ind_stocks)
            for _, row in ind_stocks.iterrows():
                selection_with_weights[row['isin']] = stock_weight
                
        return selection_with_weights
