import pandas as pd
from typing import Dict, List
from data.data_handler import DataHandler


class MCPSStrategy:
    """
    MCPS Strategy (v2 — Variant B + Group Top 50% + Optimal Concentration):

    Industry Filter:
      - Rank all industry GROUPS by % of stocks with decreasing shareholders (breadth)
      - Keep only the top 50% of groups by shareholder breadth
      - Within those groups, rank industries by % of stocks with positive MCPS change

    MCPS Signal (Variant B — signal-date M-Cap):
      mcps_now  = M-Cap at T-7 (signal date)       / curr_sh (latest available quarter)
      mcps_prev = M-Cap at T-7 minus 1 year        / prev_sh (4 quarters ago)
      Positive MCPS change = mcps_now > mcps_prev

    Stock Selection (Final Configuration):
      - Top 1000 universe by M-Cap at signal date
      - Median 21-day liquidity filter (> 0.005% of M-Cap)
      - RSI entry > 40 (weekly RSI), daily RSI exit < 39
      - Top 3 stocks by M-Cap per industry, up to 12 total (Balanced Alpha/Risk)
      - Equal weight, capped at 10% per stock
      - Quarterly rebalance (Feb/May/Aug/Nov 15th), 7-day signal lag
    """

    def __init__(self, data_handler: DataHandler,
                 group_top_pct: float = 0.50,
                 num_stocks: int = 12,
                 max_per_industry: int = 3,
                 universe_size: int = 1000,
                 liquidity_threshold_pct: float = 0.00005,
                 rsi_threshold: float = 40.0,
                 max_weight_per_stock: float = 0.10,
                 mcps_lookback_quarters: int = 4,
                 group_lookback_quarters: int = None):
        self.dh = data_handler
        self.group_top_pct = group_top_pct
        self.num_stocks = num_stocks
        self.max_per_industry = max_per_industry
        self.universe_size = universe_size
        self.liquidity_threshold_pct = liquidity_threshold_pct
        self.rsi_threshold = rsi_threshold
        self.max_weight_per_stock = max_weight_per_stock
        self.mcps_lookback_quarters = mcps_lookback_quarters
        self.group_lookback_quarters = group_lookback_quarters or 4
        self.rsi_cache = pd.DataFrame()

    # ── Quarter Label Helper ───────────────────────────────────────────────────

    # ── Quarter Label Helper ───────────────────────────────────────────────────

    def _get_quarter_labels(self, signal_date: pd.Timestamp, lookback_quarters: int):
        """Return (curr_q, prev_q) quarter labels for a given signal date and lookback."""
        year, month = signal_date.year, signal_date.month
        quarters = ["Mar", "Jun", "Sep", "Dec"]
        if month >= 2 and month < 5:    start_code, base_year = "Dec", year - 1
        elif month >= 5 and month < 8:  start_code, base_year = "Mar", year
        elif month >= 8 and month < 11: start_code, base_year = "Jun", year
        else:                           start_code, base_year = "Sep", year
        linear_map = {"Mar": 0, "Jun": 1, "Sep": 2, "Dec": 3}
        linear_curr = base_year * 4 + linear_map[start_code]
        linear_prev = linear_curr - lookback_quarters
        prev_code = quarters[linear_prev % 4]
        prev_year = linear_prev // 4
        return f"{start_code}-{base_year}", f"{prev_code}-{prev_year}"

    # ── M-Cap Lookup Helper ────────────────────────────────────────────────────

    def _get_mc_on_date(self, target_date: pd.Timestamp) -> pd.Series:
        """Return M-Cap series (indexed by isin) on the nearest trading day <= target_date."""
        available = self.dh.price_df[self.dh.price_df['date'] <= target_date]
        if available.empty:
            return pd.Series(dtype=float)
        latest = available['date'].max()
        return available[available['date'] == latest].set_index('isin')['mc']

    # ── RSI Cache ─────────────────────────────────────────────────────────────

    def precompute_rsi(self, dates: List[pd.Timestamp]):
        """Vectorized Weekly RSI (14-period) for all stocks."""
        print("Pre-computing Weekly RSI Cache for MCPS...")
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        delta = weekly_prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))

    # ── Daily RSI Exit ────────────────────────────────────────────────────────

    def check_exits(self, current_date: pd.Timestamp, portfolio) -> List[str]:
        """Sell any held stock whose weekly RSI drops below 39."""
        if self.rsi_cache.empty:
            return []
        isins = list(portfolio.keys()) if isinstance(portfolio, dict) else portfolio
        valid = [d for d in self.rsi_cache.index if d <= current_date]
        if not valid:
            return []
        rsi_date = max(valid)
        return [i for i in isins
                if i in self.rsi_cache.columns
                and pd.notna(self.rsi_cache.loc[rsi_date, i])
                and self.rsi_cache.loc[rsi_date, i] < 39]

    # ── Main Selection ────────────────────────────────────────────────────────

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """MCPS Full Selection Logic (Decoupled Signal/Group Lookbacks)."""

        # 1. Signal date (T-7)
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        sh_df = self.dh.shareholding_df
        if sh_df is None or sh_df.empty:
            return {}

        # 2. Get Quarter Labels
        # Group filter uses specified group lookback (default 4Q)
        g_curr_q, g_prev_q = self._get_quarter_labels(actual_signal_date, self.group_lookback_quarters)
        # Signal uses configurable lookback
        s_curr_q, s_prev_q = self._get_quarter_labels(actual_signal_date, self.mcps_lookback_quarters)

        def get_sh_merged(curr_q, prev_q, suffix):
            curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(
                columns={'total_shareholders': f'curr_sh_{suffix}'})
            prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(
                columns={'total_shareholders': f'prev_sh_{suffix}'})
            if curr_sh.empty or prev_sh.empty: return pd.DataFrame()
            m = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
            return m[(m[f'curr_sh_{suffix}'] > 0) & (m[f'prev_sh_{suffix}'] > 0)]

        group_m = get_sh_merged(g_curr_q, g_prev_q, 'g')
        signal_m = get_sh_merged(s_curr_q, s_prev_q, 's')

        if group_m.empty or signal_m.empty: return {}

        # 3. Industry Group Filter (Fixed 4Q)
        group_m['decreased'] = group_m['curr_sh_g'] < group_m['prev_sh_g']
        group_m['group']     = group_m['isin'].map(self.dh.isin_to_group)
        group_m = group_m.dropna(subset=['group'])
        
        group_stats = group_m.groupby('group')['decreased'].mean().reset_index()
        n_top = max(1, int(len(group_stats) * self.group_top_pct))
        top_groups = (group_stats.sort_values('decreased', ascending=False)
                      .head(n_top)['group'].tolist())
        
        # Filter signal universe by top groups
        signal_m['group']    = signal_m['isin'].map(self.dh.isin_to_group)
        signal_m['industry'] = signal_m['isin'].map(self.dh.isin_to_industry)
        signal_m = signal_m.dropna(subset=['group', 'industry'])
        signal_m = signal_m[signal_m['group'].isin(top_groups)]

        if signal_m.empty: return {}

        # 4. MCPS Ranking (Signal Date Lookback)
        mc_now  = self._get_mc_on_date(actual_signal_date)
        # mc_prev lookback should match the signal shareholder lookback (approx quarters)
        mc_prev_date = actual_signal_date - pd.DateOffset(months=3 * self.mcps_lookback_quarters)
        mc_prev = self._get_mc_on_date(mc_prev_date)

        signal_m = signal_m.copy()
        signal_m['mc_now']  = signal_m['isin'].map(mc_now)
        signal_m['mc_prev'] = signal_m['isin'].map(mc_prev)
        signal_m = signal_m.dropna(subset=['mc_now', 'mc_prev'])
        signal_m = signal_m[(signal_m['mc_now'] > 0) & (signal_m['mc_prev'] > 0)]

        signal_m['mcps_now']      = signal_m['mc_now']  / signal_m['curr_sh_s']
        signal_m['mcps_prev']     = signal_m['mc_prev'] / signal_m['prev_sh_s']
        signal_m['mcps_positive'] = signal_m['mcps_now'] > signal_m['mcps_prev']

        ind_ranked = (signal_m.groupby('industry')
                      .agg(mcps_positive_pct=('mcps_positive', 'mean'))
                      .reset_index()
                      .sort_values('mcps_positive_pct', ascending=False))
        if ind_ranked.empty: return {}

        # 5. Universe (Top 1000 by M-Cap at signal date)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty:
            return {}

        # 6. Median Liquidity Filter (21-day median traded value > 0.005% of M-Cap)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = (liq_df.groupby('isin')['traded_val']
                   .median().reset_index()
                   .rename(columns={'traded_val': 'med_val_21d'}))
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        # 7. RSI Entry Filter (weekly RSI > 40)
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty:
            return {}

        # 8. Stock Selection: iterate industries in MCPS rank order
        #    Pick top 3 by M-Cap per industry, up to 12 total
        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = (universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                          .sort_values('mc', ascending=False))
            for isin in ind_stocks.head(self.max_per_industry)['isin']:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= self.num_stocks:
                        break
            if len(selected) >= self.num_stocks:
                break

        if not selected:
            return {}

        # 9. Equal weight, capped at 10%
        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}


MCPS15Strategy = MCPSStrategy


# ── Subclass variants (for backward compatibility with test scripts) ───────────

class MCPS15Threshold(MCPS15Strategy):
    """Legacy alias — use MCPS15Strategy directly with group_top_pct parameter."""
    pass


class MCPS15StockFilter(MCPS15Strategy):
    """Legacy alias — use MCPS15Strategy directly."""
    pass
