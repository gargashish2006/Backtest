
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_12q_variation():
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

    print("Running Champion Strategy with 12-Quarter (3-Year) Shareholder Lookback & 1-Year RSNP...")
    warnings.filterwarnings('ignore')

    # Champion Params with 12-Quarter Lookback
    strat = ContrarianBreadthStrategy(dh,
                                    num_stocks=15, 
                                    max_per_industry=3,
                                    universe_size=1000, 
                                    liquidity_threshold_pct=0.00005,
                                    industry_group_top_pct=0.50, # Keep Champion
                                    industry_decrease_min_pct=0.50, # Keep Champion
                                    rsnp_threshold=0.40, # Keep Champion (Standard 1Y Lookback)
                                    shareholder_lookback_quarters=12) # VARIATION: 12 Quarters (3 Years)
                                    
    port = Portfolio(10000000)
    eng = SimEngine(dh, port, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125))
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    nav_df = pd.DataFrame(port.nav_history)
    output_path = repo_root / "outputs/lookback_12q_nav.csv"
    nav_df.to_csv(output_path, index=False)
    
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("12-QUARTER LOOKBACK VARIATION PERFORMANCE")
    print("="*60)
    print(f"{'Absolute Return':<20} : {stats['Absolute Return']}")
    print(f"{'CAGR':<20} : {stats['CAGR']}")
    print(f"{'Max Drawdown':<20} : {stats['Max Drawdown']}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']}")
    print("\n")
    
    # Comparison
    print("="*60)
    print("COMPARISON VS CHAMPION BASELINE (1 Year)")
    print("="*60)
    print(f"{'Metric':<20} | {'12-Quarter (3Y)':>15} | {'Champion (1Y)':>15}")
    print("-" * 55)
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>15} | {'22.54%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>15} | {'-41.09%':>15}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']:>15} | {'0.85':>15}")
    print("="*60)

    # Plot
    import matplotlib.pyplot as plt
    baseline_path = repo_root / "outputs/final_champion_nav.csv"
    if baseline_path.exists():
        champ_nav = pd.read_csv(baseline_path)
        champ_nav['date'] = pd.to_datetime(champ_nav['date'])
        champ_nav = champ_nav.set_index('date')['nav']
        var_nav = nav_df.set_index('date')['nav']
        plt.figure(figsize=(12, 6))
        plt.plot(champ_nav, label='Champion (1Y)', alpha=0.7)
        plt.plot(var_nav, label='Variation (3Y Lookback)', linewidth=2)
        plt.title('Strategy Comparison: Shareholder Lookback (3 Years vs 1 Year)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(repo_root / "outputs/lookback_12q_comparison.png")
        print(f"Chart saved to: {repo_root / 'outputs/lookback_12q_comparison.png'}")

if __name__ == "__main__":
    run_12q_variation()
