import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler

class CS15Strategy:
    """
    CS15 Strategy (Feb 2026 Revision):
    - Sequential Fallback Shareholder Logic (Dec-Dec, then Sep-Sep)
    - 1-Week Signal Lag for RSNP and Selection
    - Top 1000 Universe & Liquidity (0.005%)
    - RSI Entry > 40 (Calculated at Signal Date)
    - 10% Individual Stock Cap (Defensive Cash if < 10 stocks)
    - Quarterly Rebalance
    """
    
    def __init__(self, data_handler: DataHandler,
                 num_stocks: int = 15,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 industry_group_top_pct: float = 0.50,
                 industry_decrease_min_pct: float = 0.50,
                 rsnp_threshold: float = 0.40,
                 rsnp_benchmark: str = 'top_1000',
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
        self.rsnp_threshold = rsnp_threshold
        self.rsnp_benchmark = rsnp_benchmark
        self.rsi_threshold = rsi_threshold
        self.max_weight_per_stock = max_weight_per_stock
        self.shareholder_lookback_quarters = shareholder_lookback_quarters
        
        # Caches
        self.rsi_cache = pd.DataFrame()

    def precompute_rsi(self, dates: List[pd.Timestamp]):
        """Vectorized Weekly RSI calculation for all stocks."""
        print("Pre-computing Weekly RSI Cache for CS15...")
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        
        delta = weekly_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))


    def check_exits(self, current_date: pd.Timestamp, portfolio) -> List[str]:
        """Daily RSI exit: sell any held stock whose weekly RSI drops below 39."""
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
        """CS15 Full Selection Logic with 1-Week Offset."""
        # 1-Week Lag: Signal Date is 7 days prior
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_signal_date - pd.DateOffset(years=1))])

        # 1. Shareholder Filters (Global) - Current Logic: Latest available at Signal Date vs 1-year ago
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: return {}
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        # Rule 1: Group Filter (Top 50%)
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False).head(int(len(group_stats)*self.industry_group_top_pct))['group'].tolist()
        
        # Rule 2: Industry Filter (> 50%)
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries: return {}

        # 2. RSNP Momentum (Signal Date)
        if self.rsnp_benchmark == 'nifty_500':
            b_prices = self.dh.nifty_500_bench
        elif self.rsnp_benchmark == 'top_100':
            b_prices = self.dh.top_100_bench
        else:
            b_prices = self.dh.top_1000_bench
            
        if b_prices is None or b_prices.empty:
            print(f"WARNING: Benchmark {self.rsnp_benchmark} not loaded.")
            return {}
            
        b_end_qs = b_prices[b_prices['date'] <= actual_signal_date]
        b_start_qs = b_prices[b_prices['date'] <= actual_lookback_start]
        
        if b_end_qs.empty or b_start_qs.empty:
             return {}
             
        b_end = b_end_qs['index_value'].iloc[-1]
        b_start = b_start_qs['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()
        p1 = get_map(actual_signal_date)
        p0 = get_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_industries:
            isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]
            wins, total = 0, 0
            for i in isins:
                c1, c0 = p1.get(i), p0.get(i)
                if c1 and c0 and c0 > 0:
                    total += 1
                    if (c1/c0 - 1) > bench_return: wins += 1
            if total > 0: industry_rsnp.append({'industry': ind, 'rsnp': wins/total})
            
        if not industry_rsnp: return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        
        # Rule 3: RSNP > 0.4
        passed_rsnp = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold].sort_values('rsnp', ascending=False)
        if passed_rsnp.empty: return {}

        # 3. Universe & Liquidity (Signal Date) — Median traded value over 21 days
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        # 4. Weekly RSI > 40 (Signal Date)
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]
            
        if universe.empty: return {}

        # 5. Selection (Max 15 total, 3 per ind, rank by M-cap)
        selected = []
        for ind in passed_rsnp['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_stocks = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_stocks:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break
            
        if not selected: return {}
        
        # 6. Weighting (Rule 5: Equal weight but max 10% per stock)
        # weight = min(1.0/len(selected), 0.10)
        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}
