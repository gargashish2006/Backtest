import pandas as pd
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class SLT15PureMedianStrategy:
    """
    SLT15 Pure Median Variation:
    - Top 35% Industry Group ranked by MEDIAN SH Change (all stocks)
    - Top 35% Industry ranked by MEDIAN SH Change (all stocks within top groups)
    - Pick Top 5 Industries strictly by this Industry Median SH Change (all stocks)
    - Within those Top 5 Industries, select Max 3 Stocks from Top 1000 Universe ranked by individual SH Change
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

    def get_qualified_industries_with_scores(self, date: pd.Timestamp) -> List[str]:
        """Returns the list of industries passing the 35/35 median sh_change filter, ORDERED by median SH change (best first)."""
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
        # Sort ascending (most negative first) and take top 35%
        return ind_stats.sort_values(ascending=True).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        top_industries_ranked = self.get_qualified_industries_with_scores(date)
        if not top_industries_ranked: return {}

        # Pick final industries based strictly on pure median rank (already sorted)
        selected_industries = top_industries_ranked[:self.num_industries]

        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.lookback_quarters)
        univ = self.dh.get_universe(date, size=self.universe_size)
        if univ.empty or sh_trend.empty: return {}
        univ_isins = set(univ['isin'].tolist())
        
        stocks_info = []
        for _, row in sh_trend.iterrows():
            isin = row['isin']
            # Only consider top 1000 universe stocks in the selected industries
            if isin in univ_isins and isin in self.dh.isin_to_industry:
                ind = self.dh.isin_to_industry[isin]
                if ind in selected_industries:
                    stocks_info.append({
                        'isin': isin,
                        'industry': ind,
                        'sh_change_pct': (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                    })
        
        if not stocks_info: return {}
        qualified_df = pd.DataFrame(stocks_info)
        
        selection_with_weights = {}
        # Equal weight to each selected industry
        ind_weight = 1.0 / len(selected_industries)
        
        for ind in selected_industries:
            ind_stocks = qualified_df[qualified_df['industry'] == ind].sort_values('sh_change_pct', ascending=True).head(self.max_per_industry)
            if len(ind_stocks) > 0:
                stock_weight = ind_weight / len(ind_stocks)
                for _, row in ind_stocks.iterrows():
                    selection_with_weights[row['isin']] = stock_weight
                
        return selection_with_weights
