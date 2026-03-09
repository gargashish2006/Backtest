import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class ContrarianBreadthStrategy:
    """
    Champion Strategy: Contrarian Breadth Strategy
    - Universe: Top 1000 stocks by Market Cap
    - Signals: Global Shareholding Decrease (1-Year)
    - Industry Group: Top 50% by internal breadth
    - Industry: Minimum 50% breadth within top groups
    - Selection: Max 15 stocks, Max 3 per industry, Top Mcap within industry
    - Entry Filter: Weekly RSI > 40
    - Liquidity: Average daily traded value (21d) > 0.005% of Mcap
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 rsnp_threshold: float = 0.40,
                 rsnp_exit_threshold: float = 0.39,
                 rsi_threshold: float = 40,
                 rsi_exit_threshold: float = 39,
                 weekly_low_exit: bool = False,
                 month_low_exit: bool = False,
                 shareholder_lookback_quarters: int = 4,
                 min_industry_size: int = 0,
                 min_history_years: float = 0): 
        self.dh = data_handler
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.industry_group_top_pct = industry_group_top_pct
        self.industry_decrease_min_pct = industry_decrease_min_pct
        self.rsnp_threshold = rsnp_threshold
        self.rsnp_exit_threshold = rsnp_exit_threshold
        self.rsi_threshold = rsi_threshold
        self.rsi_exit_threshold = rsi_exit_threshold
        self.weekly_low_exit = weekly_low_exit
        self.month_low_exit = month_low_exit
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        self.min_industry_size = min_industry_size
        self.min_history_years = min_history_years
        self.price_lookback_days = 30
        
        # Pre-compute Caches
        self.rsi_cache = pd.DataFrame()

    def precompute_rsi(self, dates: List[pd.Timestamp]):
        """Vectorized Weekly RSI calculation for all stocks."""
        print("Pre-computing Weekly RSI Cache (Vectorized)...")
        # Ensure we have enough data (at least 20 weeks for RSI 14)
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        
        delta = weekly_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))
        print("RSI Cache Benchmark Complete.")

    def check_exits(self, current_date: pd.Timestamp, portfolio) -> List[str]:
        """Daily monitoring for Technical Exits (RSI, Lows)."""
        if not portfolio: return []
        to_sell = []
        # Handle both list of ISINs and dict of holdings
        isins = list(portfolio.keys()) if isinstance(portfolio, dict) else portfolio
        
        # Determine closest Friday for RSI
        valid_rsi_dates = [d for d in self.rsi_cache.index if d <= current_date]
        rsi_date = max(valid_rsi_dates) if valid_rsi_dates else None
        
        for isin in isins:
            # 1. RSI Exit
            if rsi_date and isin in self.rsi_cache.columns:
                if self.rsi_cache.loc[rsi_date, isin] < self.rsi_exit_threshold:
                    to_sell.append(isin)
                    continue
            
            # 2. Daily Low Exits (3-Week Weekly Low or 1-Month Daily Low)
            # These are only checked if enabled in __init__
            if self.weekly_low_exit or self.month_low_exit:
                hist = self.dh.price_df[(self.dh.price_df['isin'] == isin) & (self.dh.price_df['date'] < current_date)]
                if len(hist) < 30: continue
                
                if self.weekly_low_exit:
                    # Lowest weekly close of last 3 full weeks
                    weekly_hist = hist.set_index('date').resample('W-FRI').last().tail(3)
                    if not weekly_hist.empty:
                        min_w_low = weekly_hist['close'].min()
                        curr_p = self.dh.price_df[(self.dh.price_df['isin'] == isin) & (self.dh.price_df['date'] == current_date)]['close'].values
                        if len(curr_p) > 0 and curr_p[0] < min_w_low:
                            to_sell.append(isin)
                            continue

                if self.month_low_exit:
                    # Lowest daily close of previous month
                    prev_month_end = current_date - pd.DateOffset(months=1)
                    month_hist = hist[hist['date'] >= prev_month_end]
                    if not month_hist.empty:
                        min_m_low = month_hist['close'].min()
                        curr_p = self.dh.price_df[(self.dh.price_df['isin'] == isin) & (self.dh.price_df['date'] == current_date)]['close'].values
                        if len(curr_p) > 0 and curr_p[0] < min_m_low:
                            to_sell.append(isin)
                            continue
                            
        return to_sell

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Full rebalance logic: Filters -> Rankings -> Selection."""
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.DateOffset(years=1))])
        
        # 1. Define Universe (Top N by Mcap)
        universe = self.dh.get_universe(actual_calc_date, size=self.universe_size)
        if universe.empty: return {}
        
        # Age Filter (Original Champion = 0)
        if self.min_history_years > 0:
            age_limit = actual_calc_date - pd.DateOffset(years=int(self.min_history_years))
            eligible_isins = [isin for isin, first_date in self.dh.first_date_map.items() if first_date <= age_limit]
            universe = universe[universe['isin'].isin(eligible_isins)]

        # 2. Liquidity Filter (Average Traded Value > 0.005% of MC)
        liquidity_window = [d for d in all_dates if d <= date][-21:]
        if len(liquidity_window) < 10:
             avg_liq = universe[['isin', 'traded_val']].rename(columns={'traded_val': 'avg_val_21d'})
        else:
             liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
             avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        if universe.empty: return {}
        
        # 3. Shareholder Filter (Two-Tier)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        if self.min_industry_size > 0:
            ind_counts = sh_trend['industry'].value_counts()
            valid_inds = ind_counts[ind_counts >= self.min_industry_size].index
            sh_trend = sh_trend[sh_trend['industry'].isin(valid_inds)]
            
        if sh_trend.empty: return {}
        
        # A. Industry Group Filter (Top X%)
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        group_stats = group_stats.sort_values('decreased', ascending=False)
        top_n = max(1, int(len(group_stats) * self.industry_group_top_pct))
        top_groups = group_stats.head(top_n)['group'].tolist()
        
        # B. Industry Breadth Filter (Min X%)
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].agg(['mean', 'count']).reset_index()
        qualified_industries = ind_stats[ind_stats['mean'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}
        
        # 4. RSNP Ranking (Industry Breadth vs Top 1000)
        # Benchmark Return
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        # Robust Price Maps
        def get_robust_map(target_date):
            window = [d for d in all_dates if d <= target_date][-self.price_lookback_days:]
            subset = self.dh.price_df[self.dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            if eligible > 0:
                industry_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
                
        if not industry_rsnp: return {}
        
        ind_ranked = pd.DataFrame(industry_rsnp)
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
            
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 5. RSI Entry Filter
        if self.rsi_threshold > 0 and not self.rsi_cache.empty:
             valid_cache_dates = [d for d in self.rsi_cache.index if d <= actual_calc_date]
             if valid_cache_dates:
                 rsi_lookup_date = max(valid_cache_dates)
                 univ_isins = universe['isin'].tolist()
                 valid_isins = [i for i in univ_isins if i in self.rsi_cache.columns]
                 
                 if valid_isins:
                     rsis = self.rsi_cache.loc[rsi_lookup_date, valid_isins]
                     passed_isins = rsis[rsis > self.rsi_threshold].index.tolist()
                     universe = universe[universe['isin'].isin(passed_isins)]
        
        if universe.empty: return {}
        
        # 6. Stock Selection
        selected_isins = []
        for ind in ind_ranked['industry']:
            if len(selected_isins) >= self.num_stocks: break
            ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
            ind_universe = ind_universe.sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(self.max_per_industry)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected_isins:
                    selected_isins.append(isin)
                    if len(selected_isins) >= self.num_stocks: break
                    
        if not selected_isins: return {}
        
        # 7. Weighting
        num_final = len(selected_isins)
        if num_final >= self.num_stocks:
            w = 1.0 / num_final
        else:
            w = max(0.0667, 1.0 / num_final) if num_final > 0 else 0
            w = min(0.10, w)
            
        return {isin: w for isin in selected_isins}
