
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_rsnp_variation():
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

    print("Running Champion Strategy with RSNP Threshold = 0.5 (vs 0.4)...")
    warnings.filterwarnings('ignore')

    # Champion Params with RSNP 0.5
    strat = ContrarianBreadthStrategy(dh,
                                    num_stocks=15, 
                                    max_per_industry=3,
                                    universe_size=1000, 
                                    liquidity_threshold_pct=0.00005,
                                    industry_group_top_pct=0.50, # Keep Champion
                                    industry_decrease_min_pct=0.50, # Keep Champion
                                    rsnp_threshold=0.50, # VARIATION: 0.5 Instead of 0.4
                                    shareholder_lookback_quarters=4)
                                    
    port = Portfolio(10000000)
    eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    # Save NAV
    nav_df = pd.DataFrame(port.nav_history)
    output_path = repo_root / "outputs/rsnp_05_nav.csv"
    nav_df.to_csv(output_path, index=False)
    
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("RSNP 0.5 VARIATION PERFORMANCE")
    print("="*60)
    print(f"{'Absolute Return':<20} : {stats['Absolute Return']}")
    print(f"{'CAGR':<20} : {stats['CAGR']}")
    print(f"{'Max Drawdown':<20} : {stats['Max Drawdown']}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']}")
    print("\n")
    
    # Comparison Table
    print("="*60)
    print("COMPARISON VS CHAMPION BASELINE (RSNP 0.4)")
    print("="*60)
    print(f"{'Metric':<20} | {'RSNP 0.5':>15} | {'Champion (0.4)':>15}")
    print("-" * 55)
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'22.54%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-41.09%':>15}")
    print(f"{'Sharpe Ratio':<20} | {stats['Sharpe Ratio']:>15} | {'0.85':>15}")
    print("="*60)

    # Plot Comparison
    import matplotlib.pyplot as plt
    
    # Load Benchmark NAV if available
    baseline_path = repo_root / "outputs/final_champion_nav.csv"
    if baseline_path.exists():
        champ_nav = pd.read_csv(baseline_path)
        champ_nav['date'] = pd.to_datetime(champ_nav['date'])
        champ_nav = champ_nav.set_index('date')['nav']
        
        var_nav = nav_df.set_index('date')['nav']
        
        plt.figure(figsize=(12, 6))
        plt.plot(champ_nav, label='Champion (RSNP 0.4)', alpha=0.7)
        plt.plot(var_nav, label='Variation (RSNP 0.5)', linewidth=2)
        plt.title('Strategy Comparison: RSNP Threshold')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(repo_root / "outputs/rsnp_05_comparison.png")
        print(f"Chart saved to: {repo_root / 'outputs/rsnp_05_comparison.png'}")

if __name__ == "__main__":
    run_rsnp_variation()
