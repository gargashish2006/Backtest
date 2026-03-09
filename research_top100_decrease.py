
import pandas as pd
import warnings
from typing import Dict
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from utils.analytics import calculate_metrics

class Top100DecreaseStrategy:
    """
    1. Universe: Top 100 by Market Cap.
    2. Filter: Shareholder Count Decreased over last 4 Quarters (1 Year).
    3. Weighting: Equal Weight.
    """
    def __init__(self, data_handler: DataHandler):
        self.dh = data_handler
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Calculation dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        
        # 2. Top 100 Universe
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        universe = metrics.sort_values('mc', ascending=False).head(100)
        
        # 3. Shareholder Filter (1 Year Decrease)
        # We need to manually check 1Y decrease for these stocks
        # Using built-in helper if available, or manual logic
        sh_trend = self.dh.get_shareholder_trend(date, lookback_quarters=4)
        
        if sh_trend.empty: return {}
        
        # Filter for only those in Top 100 Universe
        univ_isins = universe['isin'].tolist()
        sh_trend = sh_trend[sh_trend['isin'].isin(univ_isins)]
        
        # Filter for Decreased
        qualified = sh_trend[sh_trend['decreased'] == True]['isin'].tolist()
        
        if not qualified: return {}
        
        # 4. Equal Weighting
        w = 1.0 / len(qualified)
        return {isin: w for isin in qualified}

class Top100BenchmarkStrategy:
    """
    Just holds the Top 100 Equal Weighted for comparison.
    """
    def __init__(self, data_handler: DataHandler):
        self.dh = data_handler
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        universe = metrics.sort_values('mc', ascending=False).head(100)
        isins = universe['isin'].tolist()
        
        if not isins: return {}
        w = 1.0 / len(isins)
        return {isin: w for isin in isins}

def run_top100_decrease():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date, end_date = "2017-05-15", "2026-02-05"
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date): rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    print("Running Top 100 Shareholder Decrease Strategy...")
    warnings.filterwarnings('ignore')

    # 1. Run Strategy
    strat = Top100DecreaseStrategy(dh)
    port = Portfolio(10000000)
    eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    strat_nav = pd.DataFrame(port.nav_history)
    strat_nav.to_csv(repo_root / "outputs/top100_decrease_nav.csv", index=False)
    strat_stats = calculate_metrics(strat_nav)
    
    # 2. Run Benchmark (Top 100 Equal Weight)
    print("Running Benchmark (Top 100 Equal Weight)...")
    bench = Top100BenchmarkStrategy(dh)
    port_b = Portfolio(10000000)
    eng_b = SimEngine(dh, port_b, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng_b.run(start_date, end_date, bench.calculate_selection, rebalance_dates, verbose=False)
    
    bench_nav = pd.DataFrame(port_b.nav_history)
    bench_nav.to_csv(repo_root / "outputs/top100_benchmark_nav.csv", index=False)
    bench_stats = calculate_metrics(bench_nav)
    
    print("\n" + "="*80)
    print("TOP 100 SHAREHOLDER DECREASE vs BENCHMARK")
    print("="*80)
    print(f"{'Metric':<20} | {'Decrease Strat':>15} | {'Benchmark (100)':>15}")
    print("-" * 55)
    print(f"{'CAGR (%)':<20} | {strat_stats['CAGR']:>15} | {bench_stats['CAGR']:>15}")
    print(f"{'Max Drawdown (%)':<20} | {strat_stats['Max Drawdown']:>15} | {bench_stats['Max Drawdown']:>15}")
    print(f"{'Sharpe Ratio':<20} : {strat_stats['Sharpe Ratio']:>15} | {bench_stats['Sharpe Ratio']:>15}")
    print("="*80)
    print(f"Final NAV (Strat): {port.nav_history[-1]['nav']:,.2f}")
    print(f"Total Costs (Strat): {eng.fee_model.total_fees:,.2f}")
    strat_taxes = sum(t['total_tax'] for t in eng.tax_man.tax_paid_history)
    print(f"Total Taxes (Strat): {strat_taxes:,.2f}")
    print("-" * 40)
    print(f"Final NAV (Bench): {port_b.nav_history[-1]['nav']:,.2f}")
    print(f"Total Costs (Bench): {eng_b.fee_model.total_fees:,.2f}")
    bench_taxes = sum(t['total_tax'] for t in eng_b.tax_man.tax_paid_history)
    print(f"Total Taxes (Bench): {bench_taxes:,.2f}")
    print("="*80)

    # Plot
    import matplotlib.pyplot as plt
    strat_nav['date'] = pd.to_datetime(strat_nav['date'])
    bench_nav['date'] = pd.to_datetime(bench_nav['date'])
    
    s_series = strat_nav.set_index('date')['nav']
    b_series = bench_nav.set_index('date')['nav']
    
    plt.figure(figsize=(12, 6))
    plt.plot(s_series, label='Top 100 (Shareholder Decrease)', linewidth=2)
    plt.plot(b_series, label='Benchmark (Top 100 Eq Wt)', alpha=0.7, linestyle='--')
    plt.title('Top 100: Shareholder Decrease vs Benchmark')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(repo_root / "outputs/top100_decrease_comparison.png")
    print(f"Chart saved to: {repo_root / 'outputs/top100_decrease_comparison.png'}")

if __name__ == "__main__":
    run_top100_decrease()
