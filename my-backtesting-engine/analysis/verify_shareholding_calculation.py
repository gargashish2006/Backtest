#!/usr/bin/env python
"""
Verify Shareholding Concentration Calculation
Shows detailed calculation for top 3 stocks by market cap for the last 2 quarters
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class ShareholdingVerifier:
    """Verify the shareholding concentration calculations"""
    
    def __init__(self, base_path=None):
        """Initialize the verifier"""
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading data...")
        self._load_data()
        
    def _load_data(self):
        """Load shareholding patterns and price data"""
        # Load shareholding patterns
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv'
        )
        
        # Load price data
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date']
        )
        
        # Load outstanding shares for company names
        self.outstanding_shares = pd.read_csv(
            self.database_path / 'outstanding_shares.csv'
        )
        
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"Loaded {len(self.price_df):,} price records")
        
    def _parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings to quarter-end dates"""
        quarter_str = str(quarter_str).strip()
        
        try:
            # Handle 'Mon-YYYY' format
            if '-' in quarter_str and len(quarter_str.split('-')) == 2:
                month_str, year_str = quarter_str.split('-')
                year = int(year_str)
                
                # Map month to quarter end date
                month_map = {
                    'Jan': (1, 31), 'Feb': (2, 28), 'Mar': (3, 31),
                    'Apr': (4, 30), 'May': (5, 31), 'Jun': (6, 30),
                    'Jul': (7, 31), 'Aug': (8, 31), 'Sep': (9, 30),
                    'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31)
                }
                
                month, day = month_map.get(month_str, (3, 31))
                
                # Handle leap years for February
                if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    day = 29
                
                return pd.Timestamp(year=year, month=month, day=day)
            
            # Handle 'Q# FY####' format
            elif 'Q' in quarter_str and 'FY' in quarter_str:
                parts = quarter_str.replace('FY', '').split('Q')
                quarter_num = int(parts[1].split()[0])
                fy_year = int(parts[1].split()[1])
                
                # Q1 FY2025 means Apr-Jun 2024, Q2 = Jul-Sep 2024, Q3 = Oct-Dec 2024, Q4 = Jan-Mar 2025
                quarter_end_months = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}
                month, day = quarter_end_months[quarter_num]
                
                # Adjust year based on quarter
                if quarter_num == 4:  # Q4 ends in March of FY year
                    year = fy_year
                else:  # Q1-Q3 end in previous calendar year
                    year = fy_year - 1
                
                return pd.Timestamp(year=year, month=month, day=day)
            
            else:
                # Try parsing as date directly
                return pd.to_datetime(quarter_str)
                
        except Exception as e:
            print(f"Warning: Could not parse quarter '{quarter_str}': {e}")
            return None
    
    def verify_last_2_quarters_top_3(self):
        """Show detailed calculation for top 3 stocks by market cap for last 2 quarters"""
        
        # Parse quarter dates
        print("\nParsing quarter dates...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Get valid data
        valid_data = self.shareholding_df.dropna(subset=['quarter_date']).copy()
        valid_data = valid_data[
            (valid_data['total_shareholders'] > 0) & 
            (valid_data['total_outstanding_shares'] > 0)
        ]
        
        # Get last 2 quarters
        unique_quarters = sorted(valid_data['quarter_date'].unique())
        last_2_quarters = unique_quarters[-2:]
        
        print(f"\nLast 2 quarters: {[q.date() for q in last_2_quarters]}")
        print("="*100)
        
        for quarter_date in last_2_quarters:
            print(f"\n{'='*100}")
            print(f"QUARTER: {quarter_date.date()} ({quarter_date.strftime('%b-%Y')})")
            print("="*100)
            
            # Get stocks for this quarter
            quarter_stocks = valid_data[valid_data['quarter_date'] == quarter_date].copy()
            
            # Get prices within +/- 10 days
            date_min = quarter_date - pd.Timedelta(days=10)
            date_max = quarter_date + pd.Timedelta(days=10)
            
            relevant_prices = self.price_df[
                (self.price_df['date'] >= date_min) & 
                (self.price_df['date'] <= date_max)
            ].copy()
            
            # Calculate date difference
            relevant_prices['date_diff'] = abs((relevant_prices['date'] - quarter_date).dt.days)
            
            # Get closest price for each ISIN
            closest_prices = relevant_prices.loc[
                relevant_prices.groupby('isin')['date_diff'].idxmin()
            ][['isin', 'date', 'close']].rename(columns={'close': 'quarter_price', 'date': 'price_date'})
            
            # Merge with shareholding data
            merged = quarter_stocks.merge(closest_prices, on='isin', how='inner')
            
            # Calculate market cap and market cap per shareholder
            merged['market_cap'] = merged['quarter_price'] * merged['total_outstanding_shares']
            merged['market_cap_cr'] = merged['market_cap'] / 10_000_000  # Convert to Crores
            merged['market_cap_per_shareholder'] = merged['market_cap'] / merged['total_shareholders']
            
            # Get top 3 by market cap
            top_3 = merged.nlargest(3, 'market_cap_cr')
            
            # Display detailed information
            for i, (idx, row) in enumerate(top_3.iterrows(), 1):
                print(f"\n{'-'*100}")
                print(f"RANK #{i}: {row['company_name']}")
                print(f"{'-'*100}")
                print(f"  ISIN: {row['isin']}")
                print(f"  Quarter: {row['quarter']}")
                print(f"  Quarter End Date: {quarter_date.date()}")
                print(f"  Price Date Used: {row['price_date'].date()} (±{abs((row['price_date'] - quarter_date).days)} days from quarter-end)")
                print(f"\n  INPUT DATA:")
                print(f"    Quarter-end Price: ₹{row['quarter_price']:,.2f}")
                print(f"    Outstanding Shares: {row['total_outstanding_shares']:,.0f}")
                print(f"    Number of Shareholders: {row['total_shareholders']:,.0f}")
                print(f"\n  CALCULATED VALUES:")
                print(f"    Market Cap = Price × Outstanding Shares")
                print(f"              = ₹{row['quarter_price']:,.2f} × {row['total_outstanding_shares']:,.0f}")
                print(f"              = ₹{row['market_cap']:,.2f}")
                print(f"              = ₹{row['market_cap_cr']:,.2f} Crores")
                print(f"\n    Market Cap per Shareholder = Market Cap / Number of Shareholders")
                print(f"                                = ₹{row['market_cap']:,.2f} / {row['total_shareholders']:,.0f}")
                print(f"                                = ₹{row['market_cap_per_shareholder']:,.2f}")
                print(f"                                = ₹{row['market_cap_per_shareholder']/100000:.2f} Lakhs")
            
            # Show quarter average
            print(f"\n{'='*100}")
            print(f"QUARTER SUMMARY:")
            print(f"  Total stocks with valid data: {len(merged)}")
            print(f"  Average Market Cap per Shareholder (all stocks): ₹{merged['market_cap_per_shareholder'].mean():,.2f}")
            print(f"                                                  = ₹{merged['market_cap_per_shareholder'].mean()/100000:.2f} Lakhs")
            print(f"  Median Market Cap per Shareholder (all stocks): ₹{merged['market_cap_per_shareholder'].median():,.2f}")
            print(f"                                                 = ₹{merged['market_cap_per_shareholder'].median()/100000:.2f} Lakhs")
            print("="*100)


def main():
    """Main execution"""
    print("="*100)
    print("SHAREHOLDING CONCENTRATION CALCULATION VERIFICATION")
    print("="*100)
    
    verifier = ShareholdingVerifier()
    verifier.verify_last_2_quarters_top_3()
    
    print("\n" + "="*100)
    print("VERIFICATION COMPLETE")
    print("="*100)


if __name__ == "__main__":
    main()
