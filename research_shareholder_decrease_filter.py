
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class StrictShareholderStrategy(ContrarianBreadthStrategy):
    """
    Inherits from ContrarianBreadthStrategy but adds a final filter:
    Selected stocks MUST have individually decreased in shareholders over the lookback period.
    """
    def calculate_selection(self, date: pd.Timestamp):
        # 1. Get standard candidates from parent (Group/Industry filters + RSNP)
        candidates = super().calculate_selection(date)
        if not candidates:
            return {}
            
        candidate_isins = list(candidates.keys())
        
        # 2. Get Individual Shareholder Trend
        # We use the same lookback as the parent strategy (default 4 quarters = 1 year)
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=self.shareholder_lookback_quarters)
        
        if sh_trend.empty:
            return {}
            
        # 3. Filter: Keep only those where 'decreased' is True
        # transform sh_trend to a set of valid ISINs
        valid_decreasers = set(sh_trend[sh_trend['decreased'] == True]['isin'])
        
        final_selection = [isin for isin in candidate_isins if isin in valid_decreasers]
        
        if not final_selection:
            return {}
            
        # Return equal weights
        weight = 1.0 / len(final_selection)
        return {isin: weight for isin in final_selection}

def run_strict_filter_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()
    
    # Quarterly Rebalance (Standard Champion Schedule)
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    rebalance_dates.sort()
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date)]

    print(f"Starting Strict Shareholder Decrease Analysis...")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")

    # Run Benchmark (Standard Champion)
    # We can just reference the known baseline or re-run for exact comparison
    # To save time, let's run just the NEW strategy and compare to known baseline numbers 
    # (CAGR: 22.54%, DD: -41.09%, Sharpe: 0.85)

    strategy = StrictShareholderStrategy(dh, num_stocks=15, max_per_industry=3)
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates,
        verbose=False
    )
    
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("STRICT SHAREHOLDER DECREASE FILTER PERFORMANCE")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
        
    print("\n" + "="*60)
    print("COMPARISON VS CHAMPION BASELINE")
    print("="*60)
    print(f"{'Metric':<20} | {'Strict Filter':<15} | {'Champion':<15}")
    print("-" * 55)
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'22.54%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-41.09%':>15}")
    print("="*60)

    # Plot Comparison
    import matplotlib.pyplot as plt
    
    # Load Benchmark NAV if available
    baseline_path = repo_root / "outputs/final_champion_nav.csv"
    if baseline_path.exists():
        champ_nav = pd.read_csv(baseline_path)
        champ_nav['date'] = pd.to_datetime(champ_nav['date'])
        champ_nav = champ_nav.set_index('date')['nav']
    else:
        print("Warning: Champion NAV file not found. Skipping plot comparison.")
        return

    strict_nav = nav_df.set_index('date')['nav']
    
    # Align dates
    combined = pd.DataFrame({'Strict Filter': strict_nav, 'Champion': champ_nav}).dropna()
    
    plt.figure(figsize=(12, 6))
    plt.plot(combined.index, combined['Champion'], label='Champion (Sector Only)', alpha=0.7)
    plt.plot(combined.index, combined['Strict Filter'], label='Strict Individual Filter', linewidth=2)
    
    plt.title('Strict Shareholder Decrease Filter vs Champion Strategy')
    plt.xlabel('Date')
    plt.ylabel('NAV')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    output_path = repo_root / "outputs/strict_vs_champion.png"
    plt.savefig(output_path)
    print(f"\nChart saved to: {output_path}")

if __name__ == "__main__":
    run_strict_filter_analysis()
