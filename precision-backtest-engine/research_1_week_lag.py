
import pandas as pd
from pathlib import Path
from typing import Dict, List
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class LaggedContrarianStrategy(ContrarianBreadthStrategy):
    """
    Variation of Champion Strategy that calculates signals (Breadth/RSNP) 
    exactly 7 days before the rebalance execution date.
    """
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # TRICK: Shift the calculation date back by 7 days
        signal_date = date - pd.Timedelta(days=7)
        
        # Use the base class logic but pass the signal_date
        # Note: We must ensure actual_calc_date logic inside the base class 
        # is relative to this signal_date.
        
        # Actually, let's override the core logic to be 100% sure of the lag impact
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_signal_date - pd.DateOffset(years=1))])
        
        # 1. Universe (Top 1000 by Signal Date)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        
        # 2. Liquidity (Calculated on Signal Date)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        avg_liq = liq_df.groupby('isin')['traded_val'].mean().reset_index().rename(columns={'traded_val': 'avg_val_21d'})
        universe = pd.merge(universe, avg_liq, on='isin', how='left')
        universe = universe[universe['avg_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        # 3. Shareholder Breadth (Calculated on Signal Date)
        sh_trend = self.dh.get_shareholder_trend(actual_signal_date, lookback_quarters=self.shareholder_lookback_quarters)
        sh_trend['group'] = sh_trend['isin'].map(self.dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        
        group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
        top_groups = group_stats.sort_values('decreased', ascending=False).head(int(len(group_stats)*0.5))['group'].tolist()
        
        ind_sh_trend = sh_trend[sh_trend['group'].isin(top_groups)]
        ind_stats = ind_sh_trend.groupby('industry')['decreased'].mean().reset_index()
        qualified_industries = ind_stats[ind_stats['decreased'] >= self.industry_decrease_min_pct]['industry'].tolist()
        
        # 4. RSNP (Calculated on Signal Date)
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_signal_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_return = (b_end / b_start) - 1
        
        def get_map(d):
            w = [x for x in all_dates if x <= d][-30:]
            return self.dh.price_df[self.dh.price_df['date'].isin(w)].sort_values('date').groupby('isin')['close'].last().to_dict()
        p1, p0 = get_map(actual_signal_date), get_map(actual_lookback_start)
        
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
        if ind_ranked.empty: return {}
        
        if self.rsnp_threshold > 0:
            ind_ranked = ind_ranked[ind_ranked['rsnp'] >= self.rsnp_threshold]
        
        if ind_ranked.empty: return {}
        ind_ranked = ind_ranked.sort_values('rsnp', ascending=False)
        
        # 5. RSI (Initial check also on signal date)
        if not self.rsi_cache.empty:
            rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
            passed_isins = [i for i in universe['isin'] if self.rsi_cache.loc[rsi_date].get(i, 0) > self.rsi_threshold]
            universe = universe[universe['isin'].isin(passed_isins)]
        
        # 6. Selection
        selected = []
        for ind in ind_ranked['industry']:
            ind_stocks = universe[universe['isin'].map(self.dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            top_3 = ind_stocks.head(self.max_per_industry)['isin'].tolist()
            for s in top_3:
                if s not in selected:
                    selected.append(s)
                    if len(selected) >= self.num_stocks: break
            if len(selected) >= self.num_stocks: break
            
        if not selected: return {}
        w = 1.0 / len(selected)
        return {isin: w for isin in selected}

def run_lag_research():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup Strategy with 1-week lag logic
    strategy = LaggedContrarianStrategy(dh)
    
    # 2. Setup Simulation
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax)
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    rebalance_dates = sorted(list(set(rebalance_dates)))
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2017-05-15") and d <= pd.Timestamp("2026-02-05")]
    
    strategy.precompute_rsi(rebalance_dates) # Caches all Fridays, lookup will handle lag
    
    # Run
    print("Running 1-Week Signal Lag Research...")
    engine.run("2017-05-15", "2026-02-05", strategy.calculate_selection, rebalance_dates, verbose=False)
    
    stats = calculate_metrics(pd.DataFrame(portfolio.nav_history))
    print("\n" + "="*40)
    print("1-WEEK SIGNAL LAG PERFORMANCE")
    print("="*40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*40)

if __name__ == "__main__":
    run_lag_research()
