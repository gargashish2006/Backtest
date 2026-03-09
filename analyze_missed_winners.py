import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def analyze_missed_winners():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
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
    
    # We will store selections and subsequent returns
    missed_stocks_analysis = []
    
    print("Running selection comparison across all rebalances...")
    
    for i in range(len(quarterly_dates) - 1):
        reb_date = quarterly_dates[i]
        next_reb = quarterly_dates[i+1]
        
        # 1. Get Selections for Avg
        strat_avg = ContrarianBreadthStrategy(dh, min_history_years=0.0, liquidity_mode='avg')
        sel_avg = list(strat_avg.calculate_selection(reb_date).keys())
        
        # 2. Get Selections for Min
        strat_min = ContrarianBreadthStrategy(dh, min_history_years=0.0, liquidity_mode='min')
        sel_min = list(strat_min.calculate_selection(reb_date).keys())
        
        # 3. Identify missed stocks (In Avg, but not Min)
        missed = [isin for isin in sel_avg if isin not in sel_min]
        
        if missed:
            # 4. Calculate Returns for missed stocks over the quarter
            # Get prices for reb_date and next_reb
            p_start_df = dh.price_df[dh.price_df['date'] <= reb_date].sort_values('date').groupby('isin').last()['close']
            p_end_df = dh.price_df[dh.price_df['date'] <= next_reb].sort_values('date').groupby('isin').last()['close']
            
            for isin in missed:
                p0 = p_start_df.get(isin)
                p1 = p_end_df.get(isin)
                name = dh.isin_to_name.get(isin, isin)
                
                if p0 and p1 and p0 > 0:
                    ret = (p1 / p0) - 1
                    missed_stocks_analysis.append({
                        'Date': reb_date.strftime('%Y-%m-%d'),
                        'ISIN': isin,
                        'Name': name,
                        'Quarter Return': ret
                    })

    df = pd.DataFrame(missed_stocks_analysis)
    if df.empty:
        print("No missed winners found.")
        return

    # Filter for "Major Performances" (e.g., > 20% in a quarter)
    winners = df[df['Quarter Return'] > 0.15].sort_values('Quarter Return', ascending=False)
    
    print("\n" + "="*60)
    print("TOP WINNERS MISSED BY 'MINIMUM' LIQUIDITY FILTER")
    print("="*60)
    print(f"{'Rebalance Date':<15} | {'Stock Name':<30} | {'Returns':<10}")
    print("-" * 60)
    for _, row in winners.head(20).iterrows():
        print(f"{row['Date']:<15} | {row['Name'][:30]:<30} | {row['Quarter Return']:.1%}")

if __name__ == "__main__":
    analyze_missed_winners()
