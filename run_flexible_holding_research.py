
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics
import warnings

def run_flexible_holding_research():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data & Strategy
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    strategy = ContrarianBreadthStrategy(dh)
    
    # 2. Define Simulation Parameters
    # We test holding periods: 3, 6, 9, 12, 18, 24 months
    # Rebalance Frequency is fixed at 3 months (Quarterly: Feb, May, Aug, Nov)
    holding_periods_months = [3, 6, 9, 12, 18, 24]
    rebalance_freq_months = 3
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    # Get all quarterly dates
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in quarterly_dates:
                        quarterly_dates.append(reb)
    quarterly_dates.sort()
    
    warnings.filterwarnings('ignore')
    
    results = {}
    
    print(f"\nRunning Flexible Holding Period Research ({start_date} to {end_date})...")
    print(f"Entry Frequency: Every 3 Months (Quarterly)")
    
    for hp in holding_periods_months:
        num_tranches = hp // rebalance_freq_months
        print(f"\n--- Testing {hp}-Month Holding Period ({num_tranches} Tranches) ---")
        
        # We need to distribute capital among N tranches
        # Total Capital = 1 Cr. Tranche Capital = 1 Cr / N
        total_capital = 10000000.0
        tranche_capital = total_capital / num_tranches
        
        tranche_navs = []
        
        for i in range(num_tranches):
            # 3. Setup Tranche i
            # Tranche 0 rebalances at index 0, 0+N, 0+2N...
            # Tranche 1 rebalances at index 1, 1+N, 1+2N...
            
            tranche_dates = [d for idx, d in enumerate(quarterly_dates) if (idx % num_tranches) == i]
            
            if not tranche_dates:
                continue
                
            print(f"  > Running Tranche {i+1}/{num_tranches} (Rebalances: {len(tranche_dates)})")
            
            port = Portfolio(tranche_capital)
            fee_model = FeeModel(0.0015, 0.005)
            tax_man = TaxManager(0.20, 0.125)
            eng = SimEngine(dh, port, fee_model, tax_man)
            
            # Run Sim for this tranche
            eng.run(start_date, end_date, strategy.calculate_selection, tranche_dates, verbose=False)
            
            # Store NAV history
            t_nav = pd.DataFrame(port.nav_history).set_index('date')['nav']
            tranche_navs.append(t_nav)
            
        # 4. Aggregate Tranches
        # Sum up NAVs day by day
        # We need a common date index. Fill fwd/bwd might be needed if start dates differ slightly?
        # SimEngine logs NAV daily for the whole period requested (start_date to end_date)
        # So indices should align.
        
        combined_nav = pd.DataFrame(tranche_navs).T.sum(axis=1).to_frame(name='nav')
        combined_nav = combined_nav.sort_index().reset_index()
        combined_nav.columns = ['date', 'nav']
        
        # Calculate Metrics
        stats = calculate_metrics(combined_nav)
        
        print(f"  >>> Result {hp}M Hold: CAGR {stats['CAGR']}, Sharpe {stats['Sharpe Ratio']}, DD {stats['Max Drawdown']}")
        results[hp] = {
            'stats': stats,
            'nav': combined_nav
        }
    
    # 5. Comparison & Plotting
    print("\n" + "="*80)
    print("FLEXIBLE HOLDING PERIOD RESULTS Summary")
    print("="*80)
    print(f"{'Hold (Months)':<15} | {'CAGR':>10} | {'Sharpe':>10} | {'Max DD':>10} | {'Auto-Rank'}")
    print("-" * 80)
    
    sorted_res = sorted(results.items(), key=lambda x: float(x[1]['stats']['Sharpe Ratio']), reverse=True)
    
    for hp, data in sorted_res:
        s = data['stats']
        print(f"{hp:<15} | {s['CAGR']:>10} | {s['Sharpe Ratio']:>10} | {s['Max Drawdown']:>10}")
        
    print("="*80)
    
    # Plot
    plt.figure(figsize=(12, 6))
    for hp, data in results.items():
        nav = data['nav']
        normalized = nav['nav'] / nav['nav'].iloc[0] * 100
        plt.plot(nav['date'], normalized, label=f"Hold {hp}M (CAGR {data['stats']['CAGR']})")
        
    plt.title("Impact of Holding Period on Champion Strategy (Staggered Tranches)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    out_img = repo_root / "outputs/flexible_holding_comparison.png"
    plt.savefig(out_img)
    print(f"Chart saved to {out_img}")
    
    # Save CSV Results
    summary_data = []
    for hp, data in results.items():
        row = data['stats']
        row['Holding_Period_Months'] = hp
        summary_data.append(row)
    
    pd.DataFrame(summary_data).to_csv(repo_root / "outputs/flexible_holding_results.csv", index=False)

if __name__ == "__main__":
    run_flexible_holding_research()
