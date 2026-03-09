import pandas as pd
import ast
from pathlib import Path

def calculate_stock_contribution(isin, name):
    root = Path(__file__).parent
    nav_path = root / "outputs/champion_full_nav.csv"
    price_path = root / "database/price_data.parquet"
    
    if not nav_path.exists():
        print("NAV file missing.")
        return
        
    df = pd.read_csv(nav_path)
    df['date'] = pd.to_datetime(df['date'])
    df['positions'] = df['positions'].apply(ast.literal_eval)
    
    # Filter for days when the stock was held
    df['held'] = df['positions'].apply(lambda x: isin in x)
    
    held_df = df[df['held']].copy()
    if held_df.empty:
        print(f"{name} was never held.")
        return
        
    # Group into continuous streaks
    held_df['streak_id'] = (held_df['held'] != held_df['held'].shift()).cumsum()
    
    # Load prices
    prices = pd.read_parquet(price_path)
    prices['date'] = pd.to_datetime(prices['date'])
    stock_prices = prices[prices['isin'] == isin][['date', 'close']].set_index('date')
    
    total_multiplier = 1.0
    
    print(f"\n--- {name} ({isin}) Contribution Analysis ---")
    print(f"{'Start Date':<12} | {'End Date':<12} | {'Entry P':<8} | {'Exit P':<8} | {'Return'}")
    print("-" * 65)
    
    for streak in held_df['streak_id'].unique():
        streak_data = held_df[held_df['streak_id'] == streak]
        start_date = streak_data['date'].min()
        end_date = streak_data['date'].max()
        
        # Get actual prices on those dates
        # Note: Rebalance usually happens on the rebalance_date.
        # However, the record_nav happens at end of day.
        # We need the price on which it was bought and price on which it was sold.
        
        # In this engine, buys happen on 'date' at 'close' price of that day.
        # Sells happen on 'date' at 'close' price.
        
        try:
            entry_price = stock_prices.loc[start_date, 'close']
            exit_price = stock_prices.loc[end_date, 'close']
            
            # Note: The NAV history records the positions AT THE END of day.
            # So if it appears on Date X, it was bought on Date X.
            # If it disappears on Date Y, it was sold on Date Y.
            # The last day it appears is end_date.
            
            # Simple point to point return
            ret = (exit_price / entry_price) - 1
            print(f"{str(start_date.date()):<12} | {str(end_date.date()):<12} | {entry_price:<8.2f} | {exit_price:<8.2f} | {ret*100:>6.2f}%")
            
            total_multiplier *= (1 + ret)
        except KeyError:
            print(f"{str(start_date.date()):<12} | {str(end_date.date()):<12} | {'N/A':<8} | {'N/A':<8} | Price Data Missing")

    print("-" * 65)
    print(f"Total Cumulative Return: {(total_multiplier - 1)*100:.2f}%")

if __name__ == "__main__":
    stocks = [
        ('INE789E01012', 'JK Paper'),
        ('INE795G01014', 'HDFC Life Insurance')
    ]
    for isin, name in stocks:
        calculate_stock_contribution(isin, name)
