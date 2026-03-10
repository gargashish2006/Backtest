"""
Data Loader - Helper functions to load and filter database data
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime


class DataLoader:
    """Helper class to load data from database files."""
    
    def __init__(self, database_path: str = "database"):
        """
        Initialize data loader.
        
        Args:
            database_path: Path to database folder (default: "database")
        """
        self.db_path = Path(database_path)
        self._master_df = None
        self._price_df = None
        self._shareholding_df = None
        self._industry_df = None
        self._stats_df = None
    
    @property
    def master_df(self) -> pd.DataFrame:
        """Load master identifiers (cached)."""
        if self._master_df is None:
            self._master_df = pd.read_csv(self.db_path / "master_identifiers.csv")
        return self._master_df
    
    @property
    def price_df(self) -> pd.DataFrame:
        """Load price data (cached)."""
        if self._price_df is None:
            self._price_df = pd.read_csv(self.db_path / "price_data.csv")
            self._price_df['date'] = pd.to_datetime(self._price_df['date'])
        return self._price_df
    
    @property
    def shareholding_df(self) -> pd.DataFrame:
        """Load shareholding patterns (cached)."""
        if self._shareholding_df is None:
            self._shareholding_df = pd.read_csv(self.db_path / "shareholding_patterns.csv")
        return self._shareholding_df
    
    @property
    def industry_df(self) -> pd.DataFrame:
        """Load industry info (cached)."""
        if self._industry_df is None:
            self._industry_df = pd.read_csv(self.db_path / "industry_info.csv")
        return self._industry_df
    
    @property
    def stats_df(self) -> pd.DataFrame:
        """Load stock statistics (cached)."""
        if self._stats_df is None:
            self._stats_df = pd.read_csv(self.db_path / "stock_statistics.csv")
        return self._stats_df
    
    def get_stock_info(self, isin: str) -> Optional[Dict]:
        """
        Get complete information for a stock.
        
        Args:
            isin: Stock ISIN
            
        Returns:
            Dictionary with stock information or None if not found
        """
        stock = self.master_df[self.master_df['isin'] == isin]
        if len(stock) == 0:
            return None
        
        return stock.iloc[0].to_dict()
    
    def get_stock_prices(
        self, 
        isin: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get price data for a stock.
        
        Args:
            isin: Stock ISIN
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            DataFrame with price data
        """
        prices = self.price_df[self.price_df['isin'] == isin].copy()
        
        if start_date:
            prices = prices[prices['date'] >= start_date]
        if end_date:
            prices = prices[prices['date'] <= end_date]
        
        return prices.sort_values('date').reset_index(drop=True)
    
    def get_stock_shareholding(self, isin: str) -> pd.DataFrame:
        """
        Get shareholding pattern for a stock.
        
        Args:
            isin: Stock ISIN
            
        Returns:
            DataFrame with shareholding data
        """
        return self.shareholding_df[self.shareholding_df['isin'] == isin].copy()
    
    def get_stocks_by_exchange(self, exchange: str) -> pd.DataFrame:
        """
        Get all stocks from a specific exchange.
        
        Args:
            exchange: Exchange name (NSE/BSE)
            
        Returns:
            DataFrame with stock information
        """
        return self.master_df[self.master_df['primary_exchange'] == exchange].copy()
    
    def get_stocks_by_industry(self, industry: str) -> pd.DataFrame:
        """
        Get all stocks in a specific industry.
        
        Args:
            industry: Industry name
            
        Returns:
            DataFrame with stock information
        """
        industry_stocks = self.industry_df[self.industry_df['industry'] == industry]
        isins = industry_stocks['isin'].tolist()
        return self.master_df[self.master_df['isin'].isin(isins)].copy()
    
    def get_all_industries(self) -> List[str]:
        """Get list of all industries."""
        return sorted(self.industry_df['industry'].unique().tolist())
    
    def get_stock_count_by_exchange(self) -> pd.Series:
        """Get count of stocks by exchange."""
        return self.master_df['primary_exchange'].value_counts()
    
    def get_stock_count_by_industry(self) -> pd.Series:
        """Get count of stocks by industry."""
        return self.industry_df['industry'].value_counts()
    
    def search_stocks(self, query: str) -> pd.DataFrame:
        """
        Search stocks by company name or symbol.
        
        Args:
            query: Search query (case-insensitive)
            
        Returns:
            DataFrame with matching stocks
        """
        query = query.lower()
        mask = (
            self.master_df['company_name'].str.lower().str.contains(query, na=False) |
            self.master_df['nse_symbol'].str.lower().str.contains(query, na=False) |
            self.master_df['primary_symbol'].str.lower().str.contains(query, na=False)
        )
        return self.master_df[mask].copy()
    
    def get_price_summary(self, isin: str) -> Dict:
        """
        Get price summary statistics for a stock.
        
        Args:
            isin: Stock ISIN
            
        Returns:
            Dictionary with summary statistics
        """
        prices = self.get_stock_prices(isin)
        
        if len(prices) == 0:
            return None
        
        return {
            'isin': isin,
            'num_records': len(prices),
            'start_date': prices['date'].min(),
            'end_date': prices['date'].max(),
            'days': (prices['date'].max() - prices['date'].min()).days,
            'first_close': prices.iloc[0]['close'],
            'last_close': prices.iloc[-1]['close'],
            'total_return_pct': ((prices.iloc[-1]['close'] - prices.iloc[0]['close']) / 
                                prices.iloc[0]['close'] * 100),
            'avg_close': prices['close'].mean(),
            'avg_volume': prices['volume'].mean(),
            'min_close': prices['close'].min(),
            'max_close': prices['close'].max()
        }
    
    def get_multiple_stocks_data(
        self, 
        isins: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Get price data for multiple stocks.
        
        Args:
            isins: List of ISINs
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Dictionary mapping ISIN to price DataFrame
        """
        result = {}
        for isin in isins:
            prices = self.get_stock_prices(isin, start_date, end_date)
            if len(prices) > 0:
                result[isin] = prices
        return result
    
    def get_top_stocks_by_data_availability(self, top_n: int = 100) -> pd.DataFrame:
        """
        Get stocks with most price data available.
        
        Args:
            top_n: Number of top stocks to return
            
        Returns:
            DataFrame with stock information sorted by data availability
        """
        stock_counts = self.price_df.groupby('isin').size().sort_values(ascending=False)
        top_isins = stock_counts.head(top_n).index.tolist()
        
        result = self.master_df[self.master_df['isin'].isin(top_isins)].copy()
        result['num_price_records'] = result['isin'].map(stock_counts)
        
        return result.sort_values('num_price_records', ascending=False).reset_index(drop=True)
