
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

repo_root = Path('/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine')
dh = DataHandler(repo_root / 'database/price_data.parquet')
dh.load_data()
dh.load_benchmarks(repo_root / 'benchmarks')

class ReconstructStrategy(ContrarianBreadthStrategy):
    def calculate_selection(self, date: pd.Timestamp) -> pd.DataFrame:
        all_dates = self.dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.DateOffset(years=1))])
        universe = self.dh.get_universe(actual_calc_date, size=1000)
        
        sh_trend = self.dh.get_shareholder_trend(date)
        sh_trend['decreased'] = sh_trend['decreased'].astype(int) # Ensure numeric
        
        # KEY: Apply shareholder breadth ONLY for top 1000 stocks
        sh_trend = sh_trend[sh_trend['isin'].isin(universe['isin'])]
        
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index().sort_values('decreased', ascending=False)
        top_groups = group_stats.head(int(len(group_stats)*0.5))['group'].tolist()
        
        ind_stats = sh_trend[sh_trend['group'].isin(top_groups)].groupby('industry')['decreased'].mean().reset_index()
        # The mean() result is in the 'decreased' column
        qualified_industries = ind_stats[ind_stats['decreased'] >= 0.50]['industry'].tolist()
        
        # RSNP
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_price(target_date):
            window = [d for d in all_dates if d <= target_date][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(window)].sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end, p_start = get_price(actual_calc_date), get_price(actual_lookback_start)
        ind_rsnp = []
        for ind in qualified_industries:
            ind_isins = [isin for isin, name in self.dh.isin_to_industry.items() if name == ind]
            wins, eligible = 0, 0
            for isin in ind_isins:
                p1, p0 = p_end.get(isin), p_start.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return: wins += 1
            if eligible > 0: ind_rsnp.append({'industry': ind, 'rsnp': wins/eligible})
        
        if not ind_rsnp: return {}
        ind_ranked = pd.DataFrame(ind_rsnp).sort_values('rsnp', ascending=False)
        ind_ranked = ind_ranked[ind_ranked['rsnp'] >= 0.40]
        
        # Selection
        selected = []
        for ind in ind_ranked['industry']:
            if len(selected) >= 15: break
            ind_universe = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_for_ind = ind_universe.head(3)['isin'].tolist()
            for isin in top_for_ind:
                if isin not in selected:
                    selected.append(isin)
                    if len(selected) >= 15: break
        
        if not selected: return {}
        return {isin: 1.0/len(selected) for isin in selected}

# Run
port = Portfolio(10000000)
fee = FeeModel(0.0015, 0.005)
tax = TaxManager(0.20, 0.125)
engine = SimEngine(dh, port, fee, tax)
# Override execute_rebalance for 1.0 NAV
def override_rebalance(self, date, target_weights, prices):
    if not target_weights:
        for isin in list(self.portfolio.holdings.keys()): self._sell_all(isin, date, prices)
        return
    total_nav = self.portfolio.cash + self.portfolio.get_market_value(prices)
    for isin, w in target_weights.items():
        price = prices.get(isin, self.portfolio.last_prices.get(isin))
        if price:
            target_val = total_nav * w
            curr_val = sum(lot.remaining_qty for lot in self.portfolio.holdings.get(isin, [])) * price
            if curr_val < target_val:
                qty = int((target_val - curr_val) / (price * 1.0065))
                if qty > 0: self._execute_trade(isin, date, price, qty, is_buy=True)
            elif curr_val > target_val:
                qty = int((curr_val - target_val) / price)
                if qty > 0: self._execute_trade(isin, date, price, qty, is_buy=False)

SimEngine._execute_rebalance = override_rebalance

strategy = ReconstructStrategy(dh)
rdates = []
all_dates = dh.get_all_dates()
for y in range(2017,2027):
    for month in [2,5,8,11]:
        d = pd.Timestamp(year=y,month=month,day=15)
        v = [dt for dt in all_dates if dt<=d]
        if v: rdates.append(max(v))
rdates.sort()
rdates = [r for r in rdates if r >= pd.Timestamp('2017-05-15') and r <= pd.Timestamp('2026-02-05')]

engine.run('2017-05-15', '2026-02-05', strategy.calculate_selection, rdates, verbose=False)
print(calculate_metrics(pd.DataFrame(port.nav_history)))
