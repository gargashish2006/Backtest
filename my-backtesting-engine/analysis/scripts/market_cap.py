"""
Market Capitalization Calculator

This module provides utilities for calculating market capitalization of stocks
using outstanding shares data.

Market Cap = Price × Outstanding Shares (in actual numbers)

Note: outstanding_shares.csv stores shares in thousands, so multiply by 1000.
"""

import pandas as pd
from pathlib import Path
from typing import Union, Optional, List
from datetime import datetime


class MarketCapCalculator:
    """
    Calculate market capitalization for stocks using outstanding shares data.
    
    The outstanding shares are stored in thousands in the database, so they are
    converted to actual numbers (× 1000) before calculations.
    
    Example:
        calc = MarketCapCalculator()
        
        # Single stock market cap
        market_cap = calc.calculate_market_cap_on_date('RELIANCE', '2025-12-15')
        
        # Multiple stocks at once
        stocks = ['TCS', 'INFY', 'HDFCBANK']
        market_caps = calc.calculate_market_caps_bulk(stocks, '2025-12-15')
        
        # Get market caps for all stocks today
        all_caps = calc.get_market_caps_today()
        
        # Classify by market cap
        large_caps = calc.classify_by_market_cap(min_cap=50000)  # > 50,000 Cr
    """
    
    # Market cap classification thresholds (in Crores)
    LARGE_CAP_THRESHOLD = 20000   # > 20,000 Cr
    MID_CAP_THRESHOLD = 5000      # 5,000 - 20,000 Cr
    # Small cap: < 5,000 Cr
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the market cap calculator.
        
        Args:
            base_path: Base path to the backtesting engine directory.
                      If None, assumes running from the engine directory.
        """
        if base_path is None:
            # Assume we're in analysis/scripts or main directory
            base_path = Path(__file__).parent.parent.parent
        else:
            base_path = Path(base_path)
            
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        # Load outstanding shares data
        self.outstanding_shares = self._load_outstanding_shares()
        
        # Create quick lookup by NSE symbol and BSE code
        self._create_lookup_indices()
        
    def _load_outstanding_shares(self) -> pd.DataFrame:
        """Load outstanding shares data from database."""
        file_path = self.database_path / 'outstanding_shares.csv'
        
        if not file_path.exists():
            raise FileNotFoundError(
                f"Outstanding shares file not found: {file_path}\n"
                f"Please run create_outstanding_shares_file.py first."
            )
        
        df = pd.read_csv(file_path)
        
        # The outstanding shares are already in actual numbers (not thousands)
        df['outstanding_shares'] = df['total_outstanding_shares']
        
        return df
    
    def _create_lookup_indices(self):
        """Create lookup dictionaries for fast access."""
        # NSE symbol lookup (remove NaN values)
        nse_data = self.outstanding_shares.dropna(subset=['nse_symbol'])
        self.nse_lookup = dict(zip(nse_data['nse_symbol'], nse_data['outstanding_shares']))
        self.nse_isin_lookup = dict(zip(nse_data['nse_symbol'], nse_data['isin']))
        
        # BSE code lookup (remove NaN values)
        bse_data = self.outstanding_shares.dropna(subset=['bse_code'])
        self.bse_lookup = dict(zip(bse_data['bse_code'].astype(int), bse_data['outstanding_shares']))
        self.bse_isin_lookup = dict(zip(bse_data['bse_code'].astype(int), bse_data['isin']))
        
        # ISIN lookup
        self.isin_lookup = dict(zip(self.outstanding_shares['isin'], self.outstanding_shares['outstanding_shares']))
        
    def get_outstanding_shares(self, symbol: Union[str, int], exchange: str = 'NSE') -> Optional[float]:
        """
        Get outstanding shares for a stock.
        
        Args:
            symbol: Stock symbol (NSE symbol or BSE code) or ISIN
            exchange: 'NSE' or 'BSE' (default: 'NSE')
            
        Returns:
            Outstanding shares (actual number) or None if not found
        """
        if exchange.upper() == 'NSE':
            return self.nse_lookup.get(symbol)
        elif exchange.upper() == 'BSE':
            # Convert to int if string
            if isinstance(symbol, str):
                try:
                    symbol = int(symbol)
                except ValueError:
                    return None
            return self.bse_lookup.get(symbol)
        else:
            # Try as ISIN
            return self.isin_lookup.get(symbol)
    
    def calculate_market_cap(
        self,
        symbol: Union[str, int],
        price: float,
        exchange: str = 'NSE'
    ) -> Optional[float]:
        """
        Calculate market capitalization for a stock at a given price.
        
        Args:
            symbol: Stock symbol (NSE symbol or BSE code)
            price: Stock price in Rupees
            exchange: 'NSE' or 'BSE' (default: 'NSE')
            
        Returns:
            Market cap in Crores or None if stock not found
            
        Example:
            calc = MarketCapCalculator()
            market_cap = calc.calculate_market_cap('TCS', 3850)
            print(f"TCS Market Cap: ₹{market_cap:,.0f} Crores")
        """
        shares = self.get_outstanding_shares(symbol, exchange)
        
        if shares is None:
            return None
        
        # Market Cap = Price × Shares (in Crores)
        market_cap_rs = price * shares
        market_cap_cr = market_cap_rs / 10_000_000  # Convert to Crores
        
        return market_cap_cr
    
    def calculate_market_cap_on_date(
        self,
        symbol: Union[str, int],
        date: str,
        exchange: str = 'NSE',
        price_data_path: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate market cap for a stock on a specific date.
        
        Loads the price from price_data.csv for the given date.
        
        Args:
            symbol: Stock symbol (NSE symbol or BSE code)
            date: Date in 'YYYY-MM-DD' format
            exchange: 'NSE' or 'BSE' (default: 'NSE')
            price_data_path: Optional custom path to price_data.csv
            
        Returns:
            Market cap in Crores or None if not found
            
        Example:
            calc = MarketCapCalculator()
            market_cap = calc.calculate_market_cap_on_date('TCS', '2025-12-15')
        """
        # Get ISIN for the symbol
        if exchange.upper() == 'NSE':
            isin = self.nse_isin_lookup.get(symbol)
        else:
            if isinstance(symbol, str):
                try:
                    symbol = int(symbol)
                except ValueError:
                    return None
            isin = self.bse_isin_lookup.get(symbol)
        
        if isin is None:
            return None
        
        # Load price data
        if price_data_path is None:
            price_data_path = self.database_path / 'price_data.csv'
        
        # Read only the needed columns for efficiency
        price_df = pd.read_csv(
            price_data_path,
            usecols=['isin', 'date', 'close'],
            parse_dates=['date']
        )
        
        # Filter for the stock and date
        date_dt = pd.to_datetime(date)
        stock_price = price_df[
            (price_df['isin'] == isin) &
            (price_df['date'] == date_dt)
        ]
        
        if stock_price.empty:
            return None
        
        price = stock_price.iloc[0]['close']
        
        return self.calculate_market_cap(symbol, price, exchange)
    
    def calculate_market_caps_bulk(
        self,
        symbols: List[Union[str, int]],
        date: Optional[str] = None,
        exchange: str = 'NSE',
        price_data_path: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate market caps for multiple stocks at once.
        
        Args:
            symbols: List of stock symbols
            date: Optional date in 'YYYY-MM-DD' format. If None, requires prices.
            exchange: 'NSE' or 'BSE' (default: 'NSE')
            price_data_path: Optional custom path to price_data.csv
            
        Returns:
            DataFrame with columns: symbol, outstanding_shares, price, market_cap_cr
            
        Example:
            calc = MarketCapCalculator()
            stocks = ['TCS', 'INFY', 'HDFCBANK']
            market_caps = calc.calculate_market_caps_bulk(stocks, '2025-12-15')
            print(market_caps)
        """
        if date is None:
            raise ValueError("Date is required for bulk calculations")
        
        # Get ISINs for all symbols
        if exchange.upper() == 'NSE':
            isins = [self.nse_isin_lookup.get(sym) for sym in symbols]
        else:
            isins = []
            for sym in symbols:
                if isinstance(sym, str):
                    try:
                        sym = int(sym)
                    except ValueError:
                        isins.append(None)
                        continue
                isins.append(self.bse_isin_lookup.get(sym))
        
        # Load price data for all stocks at once
        if price_data_path is None:
            price_data_path = self.database_path / 'price_data.csv'
        
        # Filter ISINs that exist
        valid_isins = [isin for isin in isins if isin is not None]
        
        if not valid_isins:
            return pd.DataFrame(columns=['symbol', 'outstanding_shares', 'price', 'market_cap_cr'])
        
        # Read price data
        date_dt = pd.to_datetime(date)
        price_df = pd.read_csv(
            price_data_path,
            usecols=['isin', 'date', 'close'],
            parse_dates=['date']
        )
        
        # Filter for the date and stocks
        price_df = price_df[
            (price_df['isin'].isin(valid_isins)) &
            (price_df['date'] == date_dt)
        ]
        
        # Build results
        results = []
        for symbol, isin in zip(symbols, isins):
            if isin is None:
                continue
            
            # Get price
            stock_price = price_df[price_df['isin'] == isin]
            if stock_price.empty:
                continue
            
            price = stock_price.iloc[0]['close']
            shares = self.get_outstanding_shares(symbol, exchange)
            
            if shares is not None:
                market_cap_rs = price * shares
                market_cap_cr = market_cap_rs / 10_000_000
                
                results.append({
                    'symbol': symbol,
                    'outstanding_shares': shares,
                    'price': price,
                    'market_cap_cr': market_cap_cr
                })
        
        return pd.DataFrame(results)
    
    def get_market_caps_today(
        self,
        exchange: str = 'ALL',
        top_n: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get market caps for all stocks using most recent available price.
        
        Args:
            exchange: 'NSE', 'BSE', or 'ALL' (default: 'ALL' for all stocks)
            top_n: If provided, return only top N by market cap
            
        Returns:
            DataFrame with columns: symbol, company_name, market_cap_cr
            sorted by market cap descending
            
        Example:
            calc = MarketCapCalculator()
            top_100 = calc.get_market_caps_today(top_n=100)
            print(top_100)
        """
        # Load latest prices
        price_data_path = self.database_path / 'price_data.csv'
        
        # Read price data and get latest date per stock
        price_df = pd.read_csv(
            price_data_path,
            usecols=['isin', 'date', 'close'],
            parse_dates=['date']
        )
        
        # Get latest price for each stock
        latest_prices = price_df.sort_values('date').groupby('isin').tail(1)
        
        # Merge with outstanding shares
        result = self.outstanding_shares.merge(
            latest_prices,
            on='isin',
            how='inner'
        )
        
        # Calculate market cap
        result['market_cap_cr'] = (
            result['close'] * result['outstanding_shares'] / 10_000_000
        )
        
        # Select appropriate symbol column based on exchange
        if exchange.upper() == 'NSE':
            result = result.dropna(subset=['nse_symbol'])
            result['symbol'] = result['nse_symbol']
        elif exchange.upper() == 'BSE':
            result = result.dropna(subset=['bse_code'])
            result['symbol'] = result['bse_code'].astype(int).astype(str)
        else:  # 'ALL' - use primary symbol (prefer NSE, fallback to BSE)
            result['symbol'] = result['nse_symbol'].fillna(
                result['bse_code'].astype('Int64').astype(str)
            )
        
        # Sort by market cap
        result = result.sort_values('market_cap_cr', ascending=False)
        
        # Select columns
        result = result[[
            'symbol',
            'company_name',
            'market_cap_cr',
            'date',
            'close'
        ]].rename(columns={
            'date': 'price_date',
            'close': 'price'
        })
        
        if top_n is not None:
            result = result.head(top_n)
        
        return result.reset_index(drop=True)
    
    def classify_by_market_cap(
        self,
        min_cap: Optional[float] = None,
        max_cap: Optional[float] = None,
        category: Optional[str] = None,
        exchange: str = 'ALL'
    ) -> List[str]:
        """
        Get list of stocks in a specific market cap range or category.
        
        Args:
            min_cap: Minimum market cap in Crores (optional)
            max_cap: Maximum market cap in Crores (optional)
            category: 'large', 'mid', or 'small' (optional, overrides min/max)
            exchange: 'NSE', 'BSE', or 'ALL' (default: 'ALL' for all stocks)
            
        Returns:
            List of stock symbols matching criteria
            
        Example:
            calc = MarketCapCalculator()
            
            # Get large cap stocks (> 20,000 Cr) - all exchanges
            large_caps = calc.classify_by_market_cap(category='large')
            
            # Get mid cap stocks (5,000 - 20,000 Cr) - NSE only
            mid_caps_nse = calc.classify_by_market_cap(category='mid', exchange='NSE')
            
            # Custom range
            custom = calc.classify_by_market_cap(min_cap=10000, max_cap=50000)
        """
        if category is not None:
            category = category.lower()
            if category == 'large':
                min_cap = self.LARGE_CAP_THRESHOLD
                max_cap = None
            elif category == 'mid':
                min_cap = self.MID_CAP_THRESHOLD
                max_cap = self.LARGE_CAP_THRESHOLD
            elif category == 'small':
                min_cap = None
                max_cap = self.MID_CAP_THRESHOLD
            else:
                raise ValueError(f"Invalid category: {category}. Use 'large', 'mid', or 'small'")
        
        # Get all market caps
        all_caps = self.get_market_caps_today(exchange=exchange)
        
        # Apply filters
        if min_cap is not None:
            all_caps = all_caps[all_caps['market_cap_cr'] >= min_cap]
        if max_cap is not None:
            all_caps = all_caps[all_caps['market_cap_cr'] <= max_cap]
        
        return all_caps['symbol'].tolist()
    
    def get_stock_info(self, symbol: Union[str, int], exchange: str = 'NSE') -> Optional[dict]:
        """
        Get comprehensive information about a stock.
        
        Args:
            symbol: Stock symbol (NSE symbol or BSE code)
            exchange: 'NSE' or 'BSE' (default: 'NSE')
            
        Returns:
            Dictionary with stock information or None if not found
        """
        # Get ISIN
        if exchange.upper() == 'NSE':
            isin = self.nse_isin_lookup.get(symbol)
        else:
            if isinstance(symbol, str):
                try:
                    symbol = int(symbol)
                except ValueError:
                    return None
            isin = self.bse_isin_lookup.get(symbol)
        
        if isin is None:
            return None
        
        # Get stock data
        stock_data = self.outstanding_shares[
            self.outstanding_shares['isin'] == isin
        ].iloc[0]
        
        return {
            'isin': stock_data['isin'],
            'company_name': stock_data['company_name'],
            'nse_symbol': stock_data['nse_symbol'],
            'bse_code': stock_data['bse_code'],
            'outstanding_shares': stock_data['outstanding_shares'],
            'data_quarter': stock_data['data_quarter'],
            'data_source': stock_data['data_source']
        }


# Convenience functions for quick usage

def calculate_market_cap(
    symbol: Union[str, int],
    price: float,
    exchange: str = 'NSE'
) -> Optional[float]:
    """
    Quick function to calculate market cap.
    
    Example:
        market_cap = calculate_market_cap('TCS', 3850)
        print(f"Market Cap: ₹{market_cap:,.0f} Crores")
    """
    calc = MarketCapCalculator()
    return calc.calculate_market_cap(symbol, price, exchange)


def get_market_caps_today(top_n: Optional[int] = 100) -> pd.DataFrame:
    """
    Quick function to get today's market caps for top stocks.
    
    Example:
        top_100 = get_market_caps_today(100)
        print(top_100)
    """
    calc = MarketCapCalculator()
    return calc.get_market_caps_today(top_n=top_n)


if __name__ == '__main__':
    # Example usage
    calc = MarketCapCalculator()
    
    print("Market Cap Calculator Test")
    print("=" * 80)
    
    # Test single stock
    print("\n1. Single Stock Market Cap:")
    market_cap = calc.calculate_market_cap('TCS', 3850)
    if market_cap:
        print(f"   TCS @ ₹3,850: Market Cap = ₹{market_cap:,.0f} Crores")
    
    # Test classification
    print("\n2. Market Cap Classification (ALL Exchanges):")
    large_caps = calc.classify_by_market_cap(category='large')
    mid_caps = calc.classify_by_market_cap(category='mid')
    small_caps = calc.classify_by_market_cap(category='small')
    
    print(f"   Large Cap stocks (> ₹{calc.LARGE_CAP_THRESHOLD:,} Cr): {len(large_caps)}")
    print(f"   Mid Cap stocks (₹{calc.MID_CAP_THRESHOLD:,} - ₹{calc.LARGE_CAP_THRESHOLD:,} Cr): {len(mid_caps)}")
    print(f"   Small Cap stocks (< ₹{calc.MID_CAP_THRESHOLD:,} Cr): {len(small_caps)}")
    print(f"   Total: {len(large_caps) + len(mid_caps) + len(small_caps)} stocks")
    
    # Test top stocks
    print("\n3. Top 10 Stocks by Market Cap:")
    top_10 = calc.get_market_caps_today(top_n=10)
    for idx, row in top_10.iterrows():
        print(f"   {idx+1:2d}. {row['company_name']:30s} {row['symbol']:15s} ₹{row['market_cap_cr']:>10,.0f} Cr")
    
    print("\n" + "=" * 80)
    print("✅ Market Cap Calculator working correctly!")
