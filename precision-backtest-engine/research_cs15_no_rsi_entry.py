
import pandas as pd
from pathlib import Path
from typing import Dict
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

class CS15NoRSIEntryStrategy(CS15Strategy):
    """Subclass of CS15Strategy that disables the RSI > 40 entry filter."""
    
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """CS15 Full Selection Logic with 1-Week Offset, but NO RSI Entry Filter."""
        # 1-Week Lag: Signal Date is 7 days prior
        signal_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_signal_date - pd.DateOffset(years=1))])

        # 1. Shareholder Filters (Global)
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
        b_prices = self.dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_signal_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
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

        # 3. Universe & Liquidity (Signal Date)
        universe = self.dh.get_universe(actual_signal_date, size=self.universe_size)
        liquidity_window = [d for d in all_dates if d <= actual_signal_date][-21:]
        liq_df = self.dh.price_df[self.dh.price_df['date'].isin(liquidity_window)]
        med_liq = liq_df.groupby('isin')['traded_val'].median().reset_index().rename(columns={'traded_val': 'med_val_21d'})
        universe = pd.merge(universe, med_liq, on='isin', how='left')
        universe = universe[universe['med_val_21d'] > (universe['mc'] * self.liquidity_threshold_pct)]
        
        # --- [RSI ENTRY FILTER REMOVED] ---
        # if not self.rsi_cache.empty:
        #     rsi_date = max([d for d in self.rsi_cache.index if d <= actual_signal_date])
        #     valid_rsi = self.rsi_cache.loc[rsi_date]
        #     passed_rsi = valid_rsi[valid_rsi > self.rsi_threshold].index.tolist()
        #     universe = universe[universe['isin'].isin(passed_rsi)]
            
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
        
        # 6. Weighting
        num_final = len(selected)
        weight = min(1.0 / num_final, self.max_weight_per_stock)
        return {isin: weight for isin in selected}

def run_research():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(end_date)])

    # 1. Setup Strategy (Disabled RSI Entry filter)
    # We still keep RSI cache for daily exits (unless user asked to remove both)
    # The user specifically asked about "entry only above 40 rule"
    strategy = CS15NoRSIEntryStrategy(dh)
    strategy.precompute_rsi(rdates)
    
    # 2. Setup Simulation
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005) 
    tax_manager = TaxManager(0.20, 0.125) 
    
    engine = SimEngine(dh, portfolio, fee_model, tax_manager, 
                        cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 3. Run
    print("Running CS15 (No RSI Entry Filter) Backtest...")
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
    
    # 4. Results
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*40)
    print("CS15 (NO RSI ENTRY) PERFORMANCE")
    print("="*40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*40)

if __name__ == "__main__":
    run_research()
