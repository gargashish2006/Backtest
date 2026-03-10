"""
Efficient data loader for backtesting database.
Provides optimized methods to load price data, shareholding patterns, and stock metadata.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime


class DatabaseLoader:
    """
    Centralized data loader for the backtesting database.
    Handles efficient loading and caching of market data.
    """
    
    def __init__(self, database_path: str = "database"):
        """
        Initialize the database loader.
        
        Args:
            database_path: Path to the database directory (default: "database")
        """
        self.db_path = Path(database_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database path not found: {database_path}")
        
        # Cache for loaded data
        self._price_cache = None
        self._shareholding_cache = None
        self._master_cache = None
        self._industry_cache = None
        self._stats_cache = None
    
    def load_master_identifiers(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Load master stock identifiers.
        
        Args:
            force_reload: Force reload from disk even if cached
            
        Returns:
            DataFrame with ISIN, company names, and stock codes
        """
        if self._master_cache is None or force_reload:
            self._master_cache = pd.read_csv(self.db_path / "master_identifiers.csv")
        return self._master_cache.copy()
    
    def load_price_data(
        self, 
        isins: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_reload: bool = False
    ) -> pd.DataFrame:
        """
        Load price data with optional filtering.
        
        Args:
            isins: List of ISINs to filter (None = all stocks)
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            force_reload: Force reload from disk
            
        Returns:
            DataFrame with OHLCV data
        """
        if self._price_cache is None or force_reload:
            print("Loading price data... (this may take a moment)")
            self._price_cache = pd.read_csv(
                self.db_path / "price_data.csv",
                parse_dates=['date']
            )
            print(f"✓ Loaded {len(self._price_cache):,} price records")
        
        df = self._price_cache
        
        # Apply filters
        if isins is not None:
            df = df[df['isin'].isin(isins)]
        
        if start_date is not None:
            df = df[df['date'] >= pd.to_datetime(start_date)]
        
        if end_date is not None:
            df = df[df['date'] <= pd.to_datetime(end_date)]
        
        return df.copy()
    
    def load_shareholding_patterns(
        self,
        isins: Optional[List[str]] = None,
        quarters: Optional[List[str]] = None,
        force_reload: bool = False
    ) -> pd.DataFrame:
        """
        Load shareholding pattern data.
        
        Args:
            isins: List of ISINs to filter
            quarters: List of quarters to filter
            force_reload: Force reload from disk
            
        Returns:
            DataFrame with shareholding data
        """
        if self._shareholding_cache is None or force_reload:
            self._shareholding_cache = pd.read_csv(
                self.db_path / "shareholding_patterns.csv"
            )
        
        df = self._shareholding_cache
        
        if isins is not None:
            df = df[df['isin'].isin(isins)]
        
        if quarters is not None:
            df = df[df['quarter'].isin(quarters)]
        
        return df.copy()
    
    def load_industry_info(self, force_reload: bool = False) -> pd.DataFrame:
        """Load industry classification data."""
        if self._industry_cache is None or force_reload:
            self._industry_cache = pd.read_csv(self.db_path / "industry_info.csv")
        return self._industry_cache.copy()
    
    def load_stock_statistics(self, force_reload: bool = False) -> pd.DataFrame:
        """Load pre-calculated stock statistics."""
        if self._stats_cache is None or force_reload:
            self._stats_cache = pd.read_csv(self.db_path / "stock_statistics.csv")
        return self._stats_cache.copy()
    
    def get_stocks_by_quality(self, min_quality: float = 7.0) -> List[str]:
        """
        Get list of ISINs filtered by quality score.
        
        Args:
            min_quality: Minimum quality score (0-10)
            
        Returns:
            List of ISINs meeting quality criteria
        """
        stats = self.load_stock_statistics()
        filtered = stats[stats['quality_score'] >= min_quality]
        return filtered['isin'].tolist()
    
    def get_stocks_by_industry(self, industry: str) -> List[str]:
        """
        Get list of ISINs in a specific industry.
        
        Args:
            industry: Industry name
            
        Returns:
            List of ISINs in the industry
        """
        industry_data = self.load_industry_info()
        filtered = industry_data[industry_data['industry'] == industry]
        return filtered['isin'].tolist()
    
    def get_stocks_by_industry_group(self, industry_group: str) -> List[str]:
        """
        Get list of ISINs in a specific industry group.
        
        Args:
            industry_group: Industry group name
            
        Returns:
            List of ISINs in the industry group
        """
        industry_data = self.load_industry_info()
        filtered = industry_data[industry_data['industry_group'] == industry_group]
        return filtered['isin'].tolist()
    
    def get_price_data_for_stock(
        self, 
        isin: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get price data for a single stock.
        
        Args:
            isin: Stock ISIN
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            DataFrame with price data sorted by date
        """
        df = self.load_price_data(isins=[isin], start_date=start_date, end_date=end_date)
        return df.sort_values('date').reset_index(drop=True)
    
    def get_latest_shareholding(self, isin: str) -> Optional[Dict]:
        """
        Get the latest shareholding data for a stock.
        
        Args:
            isin: Stock ISIN
            
        Returns:
            Dictionary with latest shareholding data or None
        """
        shp = self.load_shareholding_patterns(isins=[isin])
        if len(shp) == 0:
            return None
        
        latest = shp.sort_values('quarter', ascending=False).iloc[0]
        return latest.to_dict()
    
    def get_stock_info(self, isin: str) -> Dict:
        """
        Get comprehensive information for a stock.
        
        Args:
            isin: Stock ISIN
            
        Returns:
            Dictionary with stock information
        """
        master = self.load_master_identifiers()
        industry = self.load_industry_info()
        stats = self.load_stock_statistics()
        
        stock_master = master[master['isin'] == isin].iloc[0].to_dict()
        stock_industry = industry[industry['isin'] == isin].iloc[0].to_dict()
        stock_stats = stats[stats['isin'] == isin].iloc[0].to_dict()
        
        return {
            **stock_master,
            **stock_industry,
            **stock_stats
        }
    
    def clear_cache(self):
        """Clear all cached data to free memory."""
        self._price_cache = None
        self._shareholding_cache = None
        self._master_cache = None
        self._industry_cache = None
        self._stats_cache = None
        print("✓ Cache cleared")


# Convenience function for quick access
def load_database(database_path: str = "database") -> DatabaseLoader:
    """
    Create and return a DatabaseLoader instance.
    
    Args:
        database_path: Path to database directory
        
    Returns:
        DatabaseLoader instance
    """
    return DatabaseLoader(database_path)
