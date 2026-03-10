
import pandas as pd
from pathlib import Path
from typing import List, Dict
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class LockStrategy(ContrarianBreadthStrategy):
    """
    Implements a Fixed-Horizon Hard Lock.
    Positions cannot be exited during rebalance until 'lock_days' have passed.
    Emergency exits (RSI) still apply if enabled in SimEngine.
    """
    def __init__(self, data_handler, lock_days=180, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.lock_days = lock_days
        # isin -> purchase_date
        self.holdings_start = {}

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Identify Locked Stocks
        locked_isins = []
        for isin, start_dt in list(self.holdings_start.items()):
            if (date - start_dt).days < self.lock_days:
                locked_isins.append(isin)
        
        # 2. Get Top Strategy Candidates (Standard Champion logic)
        strict_selection = super().calculate_selection(date)
        
        # 3. Final Portfolio construction
        final_list = locked_isins[:self.num_stocks]
        slots_to_fill = self.num_stocks - len(final_list)
        
        if slots_to_fill > 0:
            new_candidates = [isin for isin in strict_selection.keys() if isin not in final_list]
            fresh_entries = new_candidates[:slots_to_fill]
            
            for isin in fresh_entries:
                self.holdings_start[isin] = date
                final_list.append(isin)

        # 4. Standard Cleanup
        # Remove anything that didn't make the cut from our start-date tracker
        final_set = set(final_list)
        self.holdings_start = {isin: d for isin, d in self.holdings_start.items() if isin in final_set}
        
        if not final_list: return {}
        return {isin: 1.0/len(final_list) for isin in final_list}

    def check_exits(self, date: pd.Timestamp, current_holdings: List[str]):
        # Sync: Update our tracker if SimEngine sold anything (e.g. RSI exit)
        held_set = set(current_holdings)
        self.holdings_start = {isin: d for isin, d in self.holdings_start.items() if isin in held_set}
        
        # Standard exit checks (RSI/RSNP)
        return super().check_exits(date, current_holdings)

def run_lock_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()
    
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    # Test distinct levels of "Lock"
    # 0 = No Lock (Standard)
    # 180 = 6 Month Lock (2 quarters)
    # 365 = 1 Year Lock (4 quarters)
    lock_periods = [0, 180, 365]
    results = []

    print(f"{'Lock (Days)':<12} | {'CAGR':<8} | {'Max DD':<8} | {'Sharpe':<8}")
    print("-" * 45)

    for lock in lock_periods:
        strategy = LockStrategy(dh, lock_days=lock, num_stocks=15, max_per_industry=3)
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(start_date="2017-05-15", end_date="2026-02-05", 
                  strategy_func=strategy.calculate_selection, rebalance_dates=rebalance_dates, verbose=False)
        
        metrics = calculate_metrics(pd.DataFrame(portfolio.nav_history))
        results.append({'lock': lock, 'metrics': metrics})
        print(f"{lock:<12} | {metrics['CAGR']:<8} | {metrics['Max Drawdown']:<8} | {metrics['Sharpe Ratio']:<8}")

if __name__ == "__main__":
    run_lock_analysis()
