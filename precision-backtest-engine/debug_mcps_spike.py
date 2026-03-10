"""
Diagnose the NAV spike between 2018-2019 in MCPS15-B + Group Top 50%.
Check portfolio holdings and weights at each rebalance around that period.
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()

rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
fee_model = FeeModel(0.0015, 0.005)

QUARTER_MONTH_END = {"Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12}

def get_quarter_info(signal_date, lookback_quarters=4):
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

def get_mc_on_date(target_date, price_df):
    available = price_df[price_df['date'] <= target_date]
    if available.empty: return pd.Series(dtype=float)
    latest = available['date'].max()
    return available[available['date'] == latest].set_index('isin')['mc']


# Patch the strategy to log selections
class MCPS15GroupFilterDebug:
    def __init__(self, data_handler, group_top_pct=0.50):
        self.dh = data_handler
        self.group_top_pct = group_top_pct
        self.num_stocks = 15
        self.max_per_industry = 3
        self.universe_size = 1000
        self.liquidity_threshold_pct = 0.00005
        self.rsi_threshold = 40.0
        self.max_weight_per_stock = 0.10
        self.rsi_cache = pd.DataFrame()
        self.selection_log = []

    def precompute_rsi(self, dates):
        price_pivot = self.dh.price_df.pivot(index='date', columns='isin', values='close')
        weekly_prices = price_pivot.resample('W-FRI').last().ffill()
        delta = weekly_prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.rsi_cache = 100 - (100 / (1 + rs))

    def check_exits(self, current_date, portfolio):
        if self.rsi_cache.empty: return []
        isins = list(portfolio.keys()) if isinstance(portfolio, dict) else portfolio
        valid = [d for d in self.rsi_cache.index if d <= current_date]
        if not valid: return []
        rsi_date = max(valid)
        return [i for i in isins
                if i in self.rsi_cache.columns
                and pd.notna(self.rsi_cache.loc[rsi_date, i])
                and self.rsi_cache.loc[rsi_date, i] < 39]

    def calculate_selection(self, date):
        signal_date = date - pd.Timedelta(days=7)
        actual_signal_date = max([d for d in all_dates if d <= signal_date])

        sh_df = self.dh.shareholding_df
        if sh_df is None or sh_df.empty: return {}

        curr_q, prev_q = get_quarter_info(actual_signal_date)
        curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin','total_shareholders']].rename(columns={'total_shareholders':'curr_sh'})
        prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin','total_shareholders']].rename(columns={'total_shareholders':'prev_sh'})
        if curr_sh.empty or prev_sh.empty:
            self.selection_log.append({'date': date, 'n_stocks': 0, 'stocks': [], 'note': f'No SH data: curr={curr_q}, prev={prev_q}'})
            return {}

        merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        merged = merged[(merged['curr_sh'] > 0) & (merged['prev_sh'] > 0)]
        merged['decreased'] = merged['curr_sh'] < merged['prev_sh']
        merged['group']    = merged['isin'].map(self.dh.isin_to_group)
        merged['industry'] = merged['isin'].map(self.dh.isin_to_industry)
        merged = merged.dropna(subset=['group', 'industry'])

        group_stats = merged.groupby('group')['decreased'].mean().reset_index()
        n_top = max(1, int(len(group_stats) * self.group_top_pct))
        top_groups = group_stats.sort_values('decreased', ascending=False).head(n_top)['group'].tolist()
        merged_filtered = merged[merged['group'].isin(top_groups)]
        if merged_filtered.empty:
            self.selection_log.append({'date': date, 'n_stocks': 0, 'stocks': [], 'note': 'No groups passed'})
            return {}

        mc_now  = get_mc_on_date(actual_signal_date, self.dh.price_df)
        prev_date = actual_signal_date - pd.DateOffset(years=1)
        mc_prev = get_mc_on_date(prev_date, self.dh.price_df)

        merged_filtered = merged_filtered.copy()
        merged_filtered['mc_now']  = merged_filtered['isin'].map(mc_now)
        merged_filtered['mc_prev'] = merged_filtered['isin'].map(mc_prev)
        merged_filtered = merged_filtered.dropna(subset=['mc_now','mc_prev'])
        merged_filtered = merged_filtered[(merged_filtered['mc_now'] > 0) & (merged_filtered['mc_prev'] > 0)]

        merged_filtered['mcps_now']  = merged_filtered['mc_now']  / merged_filtered['curr_sh']
        merged_filtered['mcps_prev'] = merged_filtered['mc_prev'] / merged_filtered['prev_sh']
        merged_filtered['mcps_positive'] = merged_filtered['mcps_now'] > merged_filtered['mcps_prev']

        ind_mcps = (merged_filtered.groupby('industry')
                    .agg(mcps_positive_pct=('mcps_positive', 'mean'))
                    .reset_index()
                    .sort_values('mcps_positive_pct', ascending=False))

        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        if universe.empty: return {}

        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = (liq_df.groupby('isin')['traded_val']
                   .median().reset_index()
                   .rename(columns={'traded_val': 'med_val_21d'}))
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]

        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            valid_rsi = self.rsi_cache.loc[rsi_date]
            passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
            universe = universe[universe['isin'].isin(passed_rsi)]

        if universe.empty: return {}

        selected = []
        for ind in ind_mcps['industry']:
            ind_stocks = (universe[universe['isin'].map(self.dh.isin_to_industry) == ind]
                          .sort_values('mc', ascending=False))
            for isin in ind_stocks.head(self.max_per_industry)['isin']:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break

        if not selected: return {}

        # Log the selection
        isin_to_name = {}
        try:
            day_data = self.dh.price_df[self.dh.price_df['date'] == actual_signal_date]
            if 'name' in day_data.columns:
                isin_to_name = day_data.set_index('isin')['name'].to_dict()
        except: pass

        self.selection_log.append({
            'date': date,
            'signal_date': actual_signal_date,
            'curr_q': curr_q,
            'prev_q': prev_q,
            'n_stocks': len(selected),
            'stocks': selected,
            'n_groups_passed': len(top_groups),
            'n_industries_ranked': len(ind_mcps),
        })

        weight = min(1.0 / len(selected), self.max_weight_per_stock)
        return {isin: weight for isin in selected}


print("Running MCPS15-B + Group Top 50% (debug)...")
p = Portfolio(10_000_000)
s = MCPS15GroupFilterDebug(dh, group_top_pct=0.50)
s.precompute_rsi(rdates)
e = SimEngine(dh, p, fee_model, TaxManager(0.20, 0.125),
              cash_yield_rate=0.05, cash_tax_rate=0.30)
e.run(start_date, end_date, s.calculate_selection, rdates, verbose=False)

# Print NAV around the spike (2018-2019)
nav_df = pd.DataFrame(p.nav_history)
nav_df['date'] = pd.to_datetime(nav_df['date'])
spike_window = nav_df[(nav_df['date'] >= '2018-01-01') & (nav_df['date'] <= '2019-12-31')]
print("\n── NAV around spike (2018-2019) ──")
# Show weekly samples + big moves
nav_df_w = spike_window.set_index('date').resample('W').last()
nav_df_w['pct_change'] = nav_df_w['nav'].pct_change() * 100
big_moves = nav_df_w[nav_df_w['pct_change'].abs() > 5]
print(big_moves.to_string())

# Print selection log for rebalances in that window
print("\n── Rebalance selections (2017-2019) ──")
for entry in s.selection_log:
    if entry['date'] <= pd.Timestamp('2019-12-31'):
        print(f"\nRebalance: {entry['date'].date()} | Signal: {entry.get('signal_date','?')} | "
              f"Quarters: {entry.get('curr_q','?')} vs {entry.get('prev_q','?')} | "
              f"N stocks: {entry['n_stocks']} | Groups passed: {entry.get('n_groups_passed','?')}")
        print(f"  Stocks: {entry['stocks']}")
