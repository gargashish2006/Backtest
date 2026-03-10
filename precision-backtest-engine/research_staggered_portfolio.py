import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class StaggeredStrategyWrapper:
    """
    Wraps a strategy to implement a staggered (overlapping) portfolio.
    Splits the portfolio into 4 slices: Feb, May, Aug, Nov.
    Each slice is updated once a year and held for 12 months.
    """
    def __init__(self, champion_strategy):
        self.strategy = champion_strategy
        # month_num -> selection_dict
        self.slices = {2: {}, 5: {}, 8: {}, 11: {}}
        
    def calculate_selection(self, date: pd.Timestamp):
        month = date.month
        
        # 1. Update the current season's slice
        # The strategy returns {isin: weight} where sum(weights) ~ 1.0
        new_slice = self.strategy.calculate_selection(date)
        if new_slice:
            self.slices[month] = new_slice
            
        # 2. Combine all active slices with 25% allocation each
        combined_weights = {}
        for m_num in [2, 5, 8, 11]:
            slice_data = self.slices[m_num]
            for isin, w in slice_data.items():
                # Contribution = 25% of the 1/15th weight (or whatever the strat returns)
                combined_weights[isin] = combined_weights.get(isin, 0) + (w * 0.25)
                
        return combined_weights

def run_staggered_backtest():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Staggered Strategy
    champion = ContrarianBreadthStrategy(dh)
    staggered_wrapper = StaggeredStrategyWrapper(champion)
    
    # 3. Define Quarterly Rebalance Dates
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    start_date = "2017-02-15"
    end_date = "2026-02-05"
    
    print(f"Starting STAGGERED (Combined Yearly) Backtest...")
    
    # 4. Run Backtest
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_func=staggered_wrapper.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 5. Report
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*70)
    print("STAGGERED (COMBINED YEARLY SLICES) PERFORMANCE")
    print("="*70)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    # Benchmark Comparison
    print("\n" + "="*70)
    print("COMPARISON: STAGGERED VS SINGLE-ENTRY YEARLY")
    print("="*70)
    print(f"{'Metric':<20} | {'Staggered (Comb)':<15} | {'Yearly (May Peak)':<15}")
    print("-" * 55)
    print(f"{'Abs Return (%)':<20} | {stats['Absolute Return']:>15} | {'1196.17%':>15}")
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'34.12%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-54.50%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'1.11':>15}")
    print("="*70)

if __name__ == "__main__":
    run_staggered_backtest()
