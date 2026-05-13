import pandas as pd
from typing import Dict, List
from data.data_handler import DataHandler
from strategies.cs15_strategy import CS15Strategy


class CS15RsnpStnpStrategy(CS15Strategy):
    """
    CS15_rsnp_stnp:
    Same as CS15 except industry ranking uses RSNP - STNP instead of RSNP alone.

    RSNP (unchanged from CS15):
        % of industry stocks beating NIFTY 500 over signal_date-1yr -> signal_date

    STNP (new):
        % of industry stocks beating NIFTY 500 over curr_q_end -> signal_date
        where curr_q_end = last quarter-end available at rebalance date
            Feb rebalance -> Dec 31
            May rebalance -> Mar 31
            Aug rebalance -> Jun 30
            Nov rebalance -> Sep 30

    Score = RSNP - STNP
    Filter: score > 0
    Rank:   descending by score

    rsnp_threshold parameter is ignored; threshold is hardcoded to score > 0.
    """

    @staticmethod
    def _curr_quarter_end(date: pd.Timestamp) -> pd.Timestamp:
        y, m = date.year, date.month
        if 2 <= m < 5:
            return pd.Timestamp(year=y - 1, month=12, day=31)
        if 5 <= m < 8:
            return pd.Timestamp(year=y, month=3, day=31)
        if 8 <= m < 11:
            return pd.Timestamp(year=y, month=6, day=30)
        base = y if m >= 11 else y - 1
        return pd.Timestamp(year=base, month=9, day=30)

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        actual_lookback_start = max([d for d in all_dates if d <= actual_signal_date - pd.DateOffset(years=1)])

        # STNP short-term start: last trading day <= curr_q quarter-end
        curr_q_end = self._curr_quarter_end(date)
        stnp_start_candidates = [d for d in all_dates if d <= curr_q_end]
        if not stnp_start_candidates:
            return {}
        stnp_start = max(stnp_start_candidates)

        # If stnp window is degenerate (quarter-end >= signal date), fall back to CS15
        if stnp_start >= actual_signal_date:
            return super().calculate_selection(date)

        # 1. Shareholder filters (unchanged)
        sh_trend = self.dh.get_shareholder_trend(
            actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
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
            ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        if not qualified_industries:
            return {}

        # 2. Benchmark returns
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

        def bench_return_between(start, end):
            b_e = b_prices[b_prices['date'] <= end]
            b_s = b_prices[b_prices['date'] <= start]
            if b_e.empty or b_s.empty:
                return None
            return b_e['index_value'].iloc[-1] / b_s['index_value'].iloc[-1] - 1

        bench_rsnp = bench_return_between(actual_lookback_start, actual_signal_date)
        bench_stnp = bench_return_between(stnp_start, actual_signal_date)
        if bench_rsnp is None or bench_stnp is None:
            return {}

        # Price maps (last close within 30-day window around each date)
        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)]\
                .sort_values('date').groupby('isin')['close'].last().to_dict()

        p_rsnp_end   = get_map(actual_signal_date)
        p_rsnp_start = get_map(actual_lookback_start)
        p_stnp_start = get_map(stnp_start)  # stnp_end shares actual_signal_date

        # 3. Calculate RSNP, STNP, and score per industry
        industry_scores = []
        for ind in qualified_industries:
            isins = [i for i, n in self.dh.isin_to_industry.items() if n == ind]

            rsnp_wins, rsnp_total = 0, 0
            stnp_wins, stnp_total = 0, 0

            for i in isins:
                # RSNP
                c1, c0 = p_rsnp_end.get(i), p_rsnp_start.get(i)
                if c1 and c0 and c0 > 0:
                    rsnp_total += 1
                    if (c1 / c0 - 1) > bench_rsnp:
                        rsnp_wins += 1

                # STNP
                c1s, c0s = p_rsnp_end.get(i), p_stnp_start.get(i)
                if c1s and c0s and c0s > 0:
                    stnp_total += 1
                    if (c1s / c0s - 1) > bench_stnp:
                        stnp_wins += 1

            if rsnp_total >= self.min_industry_stocks and stnp_total >= self.min_industry_stocks:
                rsnp = rsnp_wins / rsnp_total
                stnp = stnp_wins / stnp_total
                industry_scores.append({
                    'industry': ind,
                    'rsnp': rsnp,
                    'stnp': stnp,
                    'score': rsnp - stnp,
                })

        if not industry_scores:
            return {}

        ind_ranked = pd.DataFrame(industry_scores)
        passed = ind_ranked[ind_ranked['score'] > 0].sort_values('score', ascending=False)
        if passed.empty:
            return {}

        # 4. Universe & liquidity (unchanged)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index()\
            .rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[
            universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 5. RSI filter (unchanged)
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        # 6. Selection (unchanged)
        selected = []
        for ind in passed['industry']:
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

        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}
