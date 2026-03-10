import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def analyze_champion_winners():
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
    
    winners_analysis = []
    
    print("Running Champion Strategy and tracking stock returns...")
    
    # We precompute RSI for the entire period
    strat = ContrarianBreadthStrategy(dh, min_history_years=0.0)
    strat.precompute_rsi(quarterly_dates)

    for i in range(len(quarterly_dates) - 1):
        reb_date = quarterly_dates[i]
        next_reb = quarterly_dates[i+1]
        
        # Calculate Selection
        selection_dict = strat.calculate_selection(reb_date)
        if not selection_dict:
            continue
            
        selected_isins = list(selection_dict.keys())
        
        # Get prices for reb_date and next_reb
        p_start_df = dh.price_df[dh.price_df['date'] <= reb_date].sort_values('date').groupby('isin').last()['close']
        p_end_df = dh.price_df[dh.price_df['date'] <= next_reb].sort_values('date').groupby('isin').last()['close']
        
        for isin in selected_isins:
            p0 = p_start_df.get(isin)
            p1 = p_end_df.get(isin)
            name = dh.isin_to_name.get(isin, isin)
            industry = dh.isin_to_industry.get(isin, "Unknown")
            
            if p0 and p1 and p0 > 0:
                ret = (p1 / p0) - 1
                winners_analysis.append({
                    'Rebalance Date': reb_date.strftime('%Y-%m-%d'),
                    'Next Rebalance': next_reb.strftime('%Y-%m-%d'),
                    'Stock Name': name,
                    'Industry': industry,
                    'Quarterly Return': ret
                })

    df = pd.DataFrame(winners_analysis)
    if df.empty:
        print("No stock performances recorded.")
        return

    # Sort by Quarterly Return
    top_winners = df.sort_values('Quarterly Return', ascending=False)
    
    print("\n" + "="*80)
    print("TOP CHAMPION STOCK PERFORMANCES (REBALANCE TO REBALANCE)")
    print("="*80)
    print(f"{'Rebalance Date':<15} | {'Stock Name':<30} | {'Industry':<25} | {'Returns':<10}")
    print("-" * 80)
    for _, row in top_winners.head(30).iterrows():
        print(f"{row['Rebalance Date']:<15} | {row['Stock Name'][:30]:<30} | {row['Industry'][:25]:<25} | {row['Quarterly Return']:.1%}")

if __name__ == "__main__":
    analyze_champion_winners()
