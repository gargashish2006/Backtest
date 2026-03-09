
import pandas as pd
import ast
from pathlib import Path

def calculate_turnover():
    repo_root = Path(__file__).parent
    output_dir = repo_root / "outputs"
    df = pd.read_csv(output_dir / "champion_full_nav.csv")
    
    # Identify rebalance dates: where positions change significantly
    # Positions are stored as strings of dicts in 'positions' column.
    
    # 1. Parse Positions
    df['positions'] = df['positions'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else {})
    df['date'] = pd.to_datetime(df['date'])
    
    # 2. Extract Sets of ISINs per day
    # 'positions' is stored as a str(list(isins))
    df['isins'] = df['positions'].apply(lambda x: set(x) if isinstance(x, list) else set())

    
    churn_stats = []
    
    # We iterate and check when ISINs set changes compared to previous day
    # NOTE: Calendar rebalances happen quarterly. So changes usually cluster.
    # We want to count distinct "Turnover Events" or just changes.
    
    # A "Rebalance" usually means >0 changes. 
    # Let's track changes.
    
    dates = []
    added_list = []
    removed_list = []
    total_holdings = []
    
    prev_isins = set()
    
    # Skip first day
    for i in range(1, len(df)):
        curr_isins = df.iloc[i]['isins']
        curr_date = df.iloc[i]['date']
        
        # Only check if set is different
        if curr_isins != prev_isins:
            added = len(curr_isins - prev_isins)
            removed = len(prev_isins - curr_isins)
            
            # If significant activity (avoid noise if any, though daily data shouldn't have diff unless trade)
            if added > 0 or removed > 0:
                # We assume this is a rebalance or trade day
                dates.append(curr_date)
                added_list.append(added)
                removed_list.append(removed)
                total_holdings.append(len(curr_isins))
                
        prev_isins = curr_isins
        
    stats_df = pd.DataFrame({
        'Date': dates,
        'Added': added_list,
        'Removed': removed_list,
        'Total_Holdings': total_holdings
    })
    
    # Filter for Quarterly Rebalances?
    # The strategy runs quarterly. Most trades should happen then.
    # Let's see the frequency.
    
    
    # Filter for Major Rebalances
    # A true Quarterly Rebalance usually involves Replacing >= 3 stocks or significantly changing portfolio
    # Let's filter for events where Added >= 2 (to ignore single stop loss hits)
    
    major_rebalances = stats_df[stats_df['Added'] >= 2]
    
    # Exclude the very first day (Initial Entry)
    if not major_rebalances.empty and major_rebalances.iloc[0]['Added'] >= 10: 
        # First entry is usually 10-15 stocks.
        major_rebalances = major_rebalances.iloc[1:]
        
    print("\n--- Quarterly Rebalance Analysis (Champion Strategy) ---")
    print(f"Total Major Rebalances: {len(major_rebalances)}")
    print("-" * 30)
    print(f"Average Stocks ADDED per Rebalance: {major_rebalances['Added'].mean():.1f}")
    print(f"Average Stocks REMOVED per Rebalance: {major_rebalances['Removed'].mean():.1f}")
    print(f"Average Portfolio Size: {stats_df['Total_Holdings'].mean():.1f}")
    
    churn_pct = (major_rebalances['Added'].mean() + major_rebalances['Removed'].mean()) / 2 / 15 * 100
    print(f"Average Churn Rate per Quarter: {churn_pct:.1f}%")

if __name__ == "__main__":
    calculate_turnover()
