"""
Stock Screeners - Functions to screen and filter stocks
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Callable
from .data_loader import DataLoader
from .indicators import TechnicalIndicators


class StockScreener:
    """Screen stocks based on various criteria."""
    
    def __init__(self, data_loader: DataLoader):
        """
        Initialize screener.
        
        Args:
            data_loader: DataLoader instance
        """
        self.loader = data_loader
    
    def screen_by_price_range(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[str]:
        """
        Screen stocks by current price range.
        
        Args:
            min_price: Minimum price
            max_price: Maximum price
            
        Returns:
            List of ISINs matching criteria
        """
        results = []
        
        for isin in self.loader.master_df['isin']:
            prices = self.loader.get_stock_prices(isin)
            if len(prices) == 0:
                continue
            
            current_price = prices.iloc[-1]['close']
            
            if min_price and current_price < min_price:
                continue
            if max_price and current_price > max_price:
                continue
            
            results.append(isin)
        
        return results
    
    def screen_by_volume(
        self,
        min_avg_volume: Optional[float] = None,
        period: int = 20
    ) -> List[str]:
        """
        Screen stocks by average volume.
        
        Args:
            min_avg_volume: Minimum average volume
            period: Period for average calculation
            
        Returns:
            List of ISINs matching criteria
        """
        results = []
        
        for isin in self.loader.master_df['isin']:
            prices = self.loader.get_stock_prices(isin)
            if len(prices) < period:
                continue
            
            avg_volume = prices.tail(period)['volume'].mean()
            
            if min_avg_volume and avg_volume < min_avg_volume:
                continue
            
            results.append(isin)
        
        return results
    
    def screen_by_momentum(
        self,
        min_return_pct: float,
        period_days: int = 90
    ) -> pd.DataFrame:
        """
        Screen stocks by price momentum.
        
        Args:
            min_return_pct: Minimum return percentage over period
            period_days: Period in days
            
        Returns:
            DataFrame with ISIN, company name, and momentum
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) < period_days:
                continue
            
            # Get prices from period_days ago and today
            start_price = prices.iloc[-period_days]['close']
            end_price = prices.iloc[-1]['close']
            
            momentum_pct = ((end_price - start_price) / start_price) * 100
            
            if momentum_pct >= min_return_pct:
                results.append({
                    'isin': isin,
                    'company_name': row['company_name'],
                    'symbol': row['primary_symbol'],
                    f'{period_days}d_momentum_pct': momentum_pct,
                    'start_price': start_price,
                    'end_price': end_price
                })
        
        return pd.DataFrame(results).sort_values(
            f'{period_days}d_momentum_pct',
            ascending=False
        ).reset_index(drop=True)
    
    def screen_by_rsi(
        self,
        min_rsi: Optional[float] = None,
        max_rsi: Optional[float] = None,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Screen stocks by RSI.
        
        Args:
            min_rsi: Minimum RSI value
            max_rsi: Maximum RSI value
            period: RSI period
            
        Returns:
            DataFrame with ISIN, company name, and RSI
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) < period + 10:
                continue
            
            rsi = TechnicalIndicators.rsi(prices['close'], period)
            current_rsi = rsi.iloc[-1]
            
            if pd.isna(current_rsi):
                continue
            
            if min_rsi and current_rsi < min_rsi:
                continue
            if max_rsi and current_rsi > max_rsi:
                continue
            
            results.append({
                'isin': isin,
                'company_name': row['company_name'],
                'symbol': row['primary_symbol'],
                'rsi': current_rsi,
                'current_price': prices.iloc[-1]['close']
            })
        
        return pd.DataFrame(results).sort_values(
            'rsi'
        ).reset_index(drop=True)
    
    def screen_by_ma_crossover(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        lookback_days: int = 5
    ) -> pd.DataFrame:
        """
        Screen stocks with recent MA crossover.
        
        Args:
            fast_period: Fast MA period
            slow_period: Slow MA period
            lookback_days: Days to look back for crossover
            
        Returns:
            DataFrame with stocks that had recent crossover
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) < slow_period + lookback_days:
                continue
            
            fast_ma = TechnicalIndicators.sma(prices['close'], fast_period)
            slow_ma = TechnicalIndicators.sma(prices['close'], slow_period)
            
            # Check for crossover in recent days
            recent = prices.tail(lookback_days).copy()
            recent['fast_ma'] = fast_ma.tail(lookback_days).values
            recent['slow_ma'] = slow_ma.tail(lookback_days).values
            recent['signal'] = (recent['fast_ma'] > recent['slow_ma']).astype(int)
            
            # Check if crossover happened
            if recent['signal'].diff().abs().sum() > 0:
                crossover_type = "Bullish" if recent['signal'].iloc[-1] == 1 else "Bearish"
                
                results.append({
                    'isin': isin,
                    'company_name': row['company_name'],
                    'symbol': row['primary_symbol'],
                    'crossover_type': crossover_type,
                    'current_price': prices.iloc[-1]['close'],
                    'fast_ma': fast_ma.iloc[-1],
                    'slow_ma': slow_ma.iloc[-1]
                })
        
        return pd.DataFrame(results)
    
    def screen_by_breakout(
        self,
        period: int = 20,
        breakout_pct: float = 2.0
    ) -> pd.DataFrame:
        """
        Screen stocks breaking out of recent range.
        
        Args:
            period: Lookback period for range
            breakout_pct: Minimum breakout percentage above high
            
        Returns:
            DataFrame with stocks breaking out
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) < period + 1:
                continue
            
            # Get recent high (excluding today)
            recent_high = prices.iloc[-(period+1):-1]['high'].max()
            current_price = prices.iloc[-1]['close']
            
            breakout = ((current_price - recent_high) / recent_high) * 100
            
            if breakout >= breakout_pct:
                results.append({
                    'isin': isin,
                    'company_name': row['company_name'],
                    'symbol': row['primary_symbol'],
                    'current_price': current_price,
                    'recent_high': recent_high,
                    'breakout_pct': breakout
                })
        
        return pd.DataFrame(results).sort_values(
            'breakout_pct',
            ascending=False
        ).reset_index(drop=True)
    
    def screen_by_volatility(
        self,
        min_volatility: Optional[float] = None,
        max_volatility: Optional[float] = None,
        period: int = 20
    ) -> pd.DataFrame:
        """
        Screen stocks by volatility.
        
        Args:
            min_volatility: Minimum annualized volatility
            max_volatility: Maximum annualized volatility
            period: Period for volatility calculation
            
        Returns:
            DataFrame with stocks matching volatility criteria
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) < period + 10:
                continue
            
            volatility = TechnicalIndicators.volatility(prices['close'], period)
            current_vol = volatility.iloc[-1]
            
            if pd.isna(current_vol):
                continue
            
            if min_volatility and current_vol < min_volatility:
                continue
            if max_volatility and current_vol > max_volatility:
                continue
            
            results.append({
                'isin': isin,
                'company_name': row['company_name'],
                'symbol': row['primary_symbol'],
                'volatility': current_vol,
                'current_price': prices.iloc[-1]['close']
            })
        
        return pd.DataFrame(results).sort_values(
            'volatility',
            ascending=False
        ).reset_index(drop=True)
    
    def screen_custom(
        self,
        filter_func: Callable[[str, pd.DataFrame], bool],
        include_details: bool = True
    ) -> List[str]:
        """
        Screen stocks using custom filter function.
        
        Args:
            filter_func: Function that takes (isin, price_df) and returns True/False
            include_details: Whether to include stock details
            
        Returns:
            List of ISINs or DataFrame with details
        """
        results = []
        
        for idx, row in self.loader.master_df.iterrows():
            isin = row['isin']
            prices = self.loader.get_stock_prices(isin)
            
            if len(prices) == 0:
                continue
            
            if filter_func(isin, prices):
                if include_details:
                    results.append({
                        'isin': isin,
                        'company_name': row['company_name'],
                        'symbol': row['primary_symbol']
                    })
                else:
                    results.append(isin)
        
        return pd.DataFrame(results) if include_details else results
    
    def multi_criteria_screen(self, criteria: Dict) -> pd.DataFrame:
        """
        Screen stocks using multiple criteria.
        
        Args:
            criteria: Dictionary of screening criteria
                Example: {
                    'min_price': 100,
                    'max_price': 1000,
                    'min_rsi': 30,
                    'max_rsi': 70,
                    'min_momentum_90d': 10
                }
                
        Returns:
            DataFrame with stocks matching all criteria
        """
        # Start with all stocks
        candidates = set(self.loader.master_df['isin'].tolist())
        
        # Apply each criterion
        if 'min_price' in criteria or 'max_price' in criteria:
            price_filtered = self.screen_by_price_range(
                criteria.get('min_price'),
                criteria.get('max_price')
            )
            candidates = candidates.intersection(price_filtered)
        
        if 'min_rsi' in criteria or 'max_rsi' in criteria:
            rsi_df = self.screen_by_rsi(
                criteria.get('min_rsi'),
                criteria.get('max_rsi')
            )
            candidates = candidates.intersection(rsi_df['isin'].tolist())
        
        if 'min_momentum_90d' in criteria:
            momentum_df = self.screen_by_momentum(
                criteria['min_momentum_90d'],
                period_days=90
            )
            candidates = candidates.intersection(momentum_df['isin'].tolist())
        
        # Build result DataFrame
        result_rows = []
        for isin in candidates:
            stock_info = self.loader.get_stock_info(isin)
            result_rows.append({
                'isin': isin,
                'company_name': stock_info['company_name'],
                'symbol': stock_info['primary_symbol'],
                'exchange': stock_info['primary_exchange']
            })
        
        return pd.DataFrame(result_rows)
