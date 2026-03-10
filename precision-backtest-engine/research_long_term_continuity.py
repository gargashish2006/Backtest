
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

from typing import List

class ContinuityStrategy(ContrarianBreadthStrategy):
    """
    Implements 'Sticky' logic for long-term holding.
    - New Buys: Must meet strict (e.g. 50%) shareholder thresholds.
    - Existing Holds: Kept if they meet relaxed (e.g. 30%) thresholds.
    """
    def __init__(self, data_handler, relaxed_threshold=0.30, **kwargs):
        super().__init__(data_handler, **kwargs)
        self.relaxed_threshold = relaxed_threshold
        self.current_isins = []

    def check_exits(self, date: pd.Timestamp, current_holdings: List[str]):
        # Keep internal state synced with portfolio holdings
        self.current_isins = [isin for isin in current_holdings]
        to_sell = super().check_exits(date, current_holdings)
        for isin in to_sell:
            if isin in self.current_isins:
                self.current_isins.remove(isin)
        return to_sell

    def calculate_selection(self, date: pd.Timestamp):
        # 1. Get Shareholder Stats for the date
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        if sh_trend.empty: 
            return {isin: 1.0/len(self.current_isins) for isin in self.current_isins} if self.current_isins else {}
            
        sh_trend['industry'] = sh_trend['isin'].map(self.dh.isin_to_industry)
        ind_stats = sh_trend.groupby('industry')['decreased'].mean().to_dict()

        # 2. Identify "Sticky" Holds
        # Any currently held stock that still meets the RELAXED threshold stays.
        protected_isins = []
        for isin in self.current_isins:
            industry = self.dh.isin_to_industry.get(isin)
            i_val = ind_stats.get(industry, 0)
            
            if i_val >= self.relaxed_threshold:
                protected_isins.append(isin)

        # 3. Fill remaining slots with STRICT candidates (Top 50%/50% logic)
        slots_to_fill = self.num_stocks - len(protected_isins)
        
        final_list = protected_isins[:self.num_stocks]
        if slots_to_fill > 0:
            # We call the parent's calculate_selection to get the best STRICT signals
            strict_selection = super().calculate_selection(date)
            new_candidates = [isin for isin in strict_selection.keys() if isin not in final_list]
            
            # Add up to available slots
            final_list.extend(new_candidates[:slots_to_fill])

        self.current_isins = final_list
        if not final_list: return {}
        
        return {isin: 1.0/len(final_list) for isin in final_list}

def run_continuity_analysis():
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

    # Test distinct levels of "Stickiness"
    # 0.50 = Strict (No continuity, same as Champion)
    # 0.30 = Moderate Sticky
    # 0.10 = Very Sticky
    thresholds = [0.50, 0.30, 0.10]
    results = []

    print(f"{'Threshold':<10} | {'CAGR':<8} | {'Max DD':<8} | {'Sharpe':<8}")
    print("-" * 45)

    for thresh in thresholds:
        strategy = ContinuityStrategy(dh, relaxed_threshold=thresh, num_stocks=15, max_per_industry=3)
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(start_date="2017-05-15", end_date="2026-02-05", 
                  strategy_func=strategy.calculate_selection, rebalance_dates=rebalance_dates, verbose=False)
        
        metrics = calculate_metrics(pd.DataFrame(portfolio.nav_history))
        results.append({'threshold': thresh, 'metrics': metrics})
        print(f"{thresh:<10.2f} | {metrics['CAGR']:<8} | {metrics['Max Drawdown']:<8} | {metrics['Sharpe Ratio']:<8}")

if __name__ == "__main__":
    run_continuity_analysis()
