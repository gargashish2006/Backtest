import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data.data_handler import DataHandler
from strategies.cs15_strategy import CS15Strategy


class CS15DelayedStrategy(CS15Strategy):
    """
    CS15_delayed: identical to CS15 except the RSNP momentum window is anchored
    to the shareholder report quarter-end (curr_q) instead of the signal date.

    RSNP window:
        end   = last trading day <= quarter-end of curr_q
        start = last trading day <= (end - 1 year)

    Everything else — shareholder filters, liquidity, RSI entry, selection,
    weighting — is inherited unchanged from CS15Strategy.
    """

    @staticmethod
    def _curr_quarter_end(date: pd.Timestamp) -> pd.Timestamp:
        """Mirror of the curr_q selection in DataHandler.get_shareholder_trend,
        returning the calendar quarter-end date for that quarter label."""
        y, m = date.year, date.month
        if 2 <= m < 5:
            return pd.Timestamp(year=y - 1, month=12, day=31)
        if 5 <= m < 8:
            return pd.Timestamp(year=y, month=3, day=31)
        if 8 <= m < 11:
            return pd.Timestamp(year=y, month=6, day=30)
        # Nov or Jan
        base_year = y if m >= 11 else y - 1
        return pd.Timestamp(year=base_year, month=9, day=30)

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1-week lag on signal (unchanged from CS15)
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        # Shareholder-aligned RSNP window
        curr_q_end = self._curr_quarter_end(date)
        rsnp_end_candidates = [d for d in all_dates if d <= curr_q_end]
        if not rsnp_end_candidates:
            return {}
        rsnp_end = max(rsnp_end_candidates)
        rsnp_start_target = rsnp_end - pd.DateOffset(years=1)
        rsnp_start_candidates = [d for d in all_dates if d <= rsnp_start_target]
        if not rsnp_start_candidates:
            return {}
        rsnp_start = max(rsnp_start_candidates)

        # 1. Shareholder filters (unchanged)
        sh_trend = self.dh.get_shareholder_trend(
            actual_signal_date,
            lookback_quarters=self.shareholder_lookback_quarters,
        )
        if sh_trend.empty:
            return {}

        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)

        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False)\
            .head(int(len(group_stats) * self.industry_group_top_pct))['group'].tolist()

        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[
            ind_stats['decreased'] >= self.industry_decrease_min_pct
        ]['industry'].tolist()
        if not qualified_industries:
            return {}

        # 2. RSNP momentum — window ends at curr_q quarter-end
        if self.rsnp_benchmark == 'nifty_500':
            b_prices = self.dh.nifty_500_bench
        elif self.rsnp_benchmark == 'top_100':
            b_prices = self.dh.top_100_bench
        elif self.rsnp_benchmark == 'top_1000':
            b_prices = self.dh.top_1000_bench
        else:
            b_prices = getattr(self.dh, 'indices_bench', {}).get(self.rsnp_benchmark)

        if b_prices is None or b_prices.empty:
            print(f"WARNING: Benchmark {self.rsnp_benchmark} not loaded.")
            return {}

        b_end_qs = b_prices[b_prices['date'] <= rsnp_end]
        b_start_qs = b_prices[b_prices['date'] <= rsnp_start]
        if b_end_qs.empty or b_start_qs.empty:
            return {}
        b_end = b_end_qs['index_value'].iloc[-1]
        b_start = b_start_qs['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1

        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)]\
                .sort_values('date').groupby('isin')['close'].last().to_dict()

        p1 = get_map(rsnp_end)
        p0 = get_map(rsnp_start)

        industry_rsnp = []
        for ind in qualified_industries:
            isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]
            wins, total = 0, 0
            for i in isins:
                c1, c0 = p1.get(i), p0.get(i)
                if c1 and c0 and c0 > 0:
                    total += 1
                    if (c1 / c0 - 1) > bench_return:
                        wins += 1
            if total >= self.min_industry_stocks:
                industry_rsnp.append({'industry': ind, 'rsnp': wins / total})

        if not industry_rsnp:
            return {}
        ind_ranked = pd.DataFrame(industry_rsnp)
        passed_rsnp = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]\
            .sort_values('rsnp', ascending=False)
        if passed_rsnp.empty:
            return {}

        # 3. Universe & liquidity at signal date (unchanged)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index()\
            .rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[
            universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)
        ]

        # 4. Weekly RSI > threshold at signal date (unchanged)
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        # 5. Selection (unchanged)
        selected = []
        for ind in passed_rsnp['industry']:
            ind_stocks = universe[
                universe['isin'].map(self.dh.isin_to_industry) == ind
            ].sort_values('mc', ascending=False)
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

        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}
