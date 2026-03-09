
import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.industry_qualification_strategy import IndustryQualificationStrategy
from utils.analytics import calculate_metrics

def run_industry_qualification_full():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # FULL PERIOD
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
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
    
    variations = {
        'Var1_Rebalance': 'rebalance',
        'Var2_CashDrift': 'cash'
    }
    
    print(f"\nRunning Industry Qualification Research (FULL PERIOD {start_date} to {end_date})...")
    
    results = {}
    
    for name, mode in variations.items():
        print(f"\n--- Running Variation: {name} ---")
        
        # Initialize Portfolio FIRST
        port = Portfolio(10000000)
        
        # Initialize Strategy with Portfolio Reference
        strategy = IndustryQualificationStrategy(dh, portfolio=port, allocation_mode=mode)
        
        fee_model = FeeModel(0.0015, 0.005)
        tax_man = TaxManager(0.20, 0.125)
        eng = SimEngine(dh, port, fee_model, tax_man)
        
        eng.run(start_date, end_date, strategy.calculate_selection, quarterly_dates, verbose=True)
        
        nav_df = pd.DataFrame(port.nav_history)
        stats = calculate_metrics(nav_df)
        
        print(f"  >>> Result {name}: CAGR {stats['CAGR']}, Sharpe {stats['Sharpe Ratio']}, DD {stats['Max Drawdown']}")
        
        results[name] = {
            'stats': stats,
            'nav': nav_df
        }
        
    # 5. Summary & Save
    print("\n" + "="*80)
    print("INDUSTRY QUALIFICATION RESULTS (FULL PERIOD 2017-2026)")
    print("="*80)
    print(f"{'Variation':<20} | {'CAGR':>10} | {'Sharpe':>10} | {'Max DD':>10}")
    print("-" * 80)
    
    sorted_res = sorted(results.items(), key=lambda x: float(x[1]['stats']['Sharpe Ratio']), reverse=True)
    
    for name, data in sorted_res:
        s = data['stats']
        print(f"{name:<20} | {s['CAGR']:>10} | {s['Sharpe Ratio']:>10} | {s['Max Drawdown']:>10}")
    print("="*80)
    
    # Save Results
    summary_data = []
    for name, data in results.items():
        row = data['stats']
        row['Variation'] = name
        summary_data.append(row)
        
        # Save NAV
        data['nav'].to_csv(repo_root / f"outputs/ind_qual_full_{name}_nav.csv", index=False)
    
    pd.DataFrame(summary_data).to_csv(repo_root / "outputs/ind_qual_full_results.csv", index=False)

if __name__ == "__main__":
    run_industry_qualification_full()
