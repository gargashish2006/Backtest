"""
Technical Indicators - Common technical analysis indicators
"""

import pandas as pd
import numpy as np
from typing import Optional


class TechnicalIndicators:
    """Calculate common technical indicators."""
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average.
        
        Args:
            data: Price series
            period: Moving average period
            
        Returns:
            SMA series
        """
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average.
        
        Args:
            data: Price series
            period: Moving average period
            
        Returns:
            EMA series
        """
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index.
        
        Args:
            data: Price series
            period: RSI period (default: 14)
            
        Returns:
            RSI series
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(
        data: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> pd.DataFrame:
        """
        MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price series
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)
            
        Returns:
            DataFrame with macd, signal, and histogram columns
        """
        fast_ema = data.ewm(span=fast_period, adjust=False).mean()
        slow_ema = data.ewm(span=slow_period, adjust=False).mean()
        
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return pd.DataFrame({
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        })
    
    @staticmethod
    def bollinger_bands(
        data: pd.Series,
        period: int = 20,
        num_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Bollinger Bands.
        
        Args:
            data: Price series
            period: Moving average period (default: 20)
            num_std: Number of standard deviations (default: 2.0)
            
        Returns:
            DataFrame with upper, middle, and lower bands
        """
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        })
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Average True Range.
        
        Args:
            df: DataFrame with high, low, close columns
            period: ATR period (default: 14)
            
        Returns:
            ATR series
        """
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def stochastic(
        df: pd.DataFrame,
        period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3
    ) -> pd.DataFrame:
        """
        Stochastic Oscillator.
        
        Args:
            df: DataFrame with high, low, close columns
            period: Lookback period (default: 14)
            smooth_k: %K smoothing (default: 3)
            smooth_d: %D smoothing (default: 3)
            
        Returns:
            DataFrame with %K and %D columns
        """
        lowest_low = df['low'].rolling(window=period).min()
        highest_high = df['high'].rolling(window=period).max()
        
        k = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        k = k.rolling(window=smooth_k).mean()
        d = k.rolling(window=smooth_d).mean()
        
        return pd.DataFrame({
            'k': k,
            'd': d
        })
    
    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Average Directional Index.
        
        Args:
            df: DataFrame with high, low, close columns
            period: ADX period (default: 14)
            
        Returns:
            ADX series
        """
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        pos_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        neg_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        tr = TechnicalIndicators.atr(df, period=1)
        
        pos_di = 100 * (pos_dm.rolling(window=period).mean() / tr.rolling(window=period).mean())
        neg_di = 100 * (neg_dm.rolling(window=period).mean() / tr.rolling(window=period).mean())
        
        dx = 100 * (abs(pos_di - neg_di) / (pos_di + neg_di))
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """
        On-Balance Volume.
        
        Args:
            df: DataFrame with close and volume columns
            
        Returns:
            OBV series
        """
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return obv
    
    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series:
        """
        Volume Weighted Average Price.
        
        Args:
            df: DataFrame with high, low, close, volume columns
            
        Returns:
            VWAP series
        """
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    @staticmethod
    def returns(data: pd.Series, periods: int = 1) -> pd.Series:
        """
        Calculate returns.
        
        Args:
            data: Price series
            periods: Number of periods (default: 1 for daily returns)
            
        Returns:
            Returns series
        """
        return data.pct_change(periods=periods)
    
    @staticmethod
    def volatility(data: pd.Series, period: int = 20) -> pd.Series:
        """
        Calculate rolling volatility (standard deviation of returns).
        
        Args:
            data: Price series
            period: Rolling window period (default: 20)
            
        Returns:
            Volatility series
        """
        returns = data.pct_change()
        return returns.rolling(window=period).std() * np.sqrt(252)  # Annualized
    
    @staticmethod
    def momentum(data: pd.Series, period: int = 10) -> pd.Series:
        """
        Price momentum (rate of change).
        
        Args:
            data: Price series
            period: Lookback period (default: 10)
            
        Returns:
            Momentum series
        """
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all common technical indicators to DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with all indicators added
        """
        result = df.copy()
        
        # Moving averages
        result['sma_20'] = TechnicalIndicators.sma(df['close'], 20)
        result['sma_50'] = TechnicalIndicators.sma(df['close'], 50)
        result['sma_200'] = TechnicalIndicators.sma(df['close'], 200)
        result['ema_12'] = TechnicalIndicators.ema(df['close'], 12)
        result['ema_26'] = TechnicalIndicators.ema(df['close'], 26)
        
        # RSI
        result['rsi'] = TechnicalIndicators.rsi(df['close'])
        
        # MACD
        macd_df = TechnicalIndicators.macd(df['close'])
        result['macd'] = macd_df['macd']
        result['macd_signal'] = macd_df['signal']
        result['macd_histogram'] = macd_df['histogram']
        
        # Bollinger Bands
        bb_df = TechnicalIndicators.bollinger_bands(df['close'])
        result['bb_upper'] = bb_df['upper']
        result['bb_middle'] = bb_df['middle']
        result['bb_lower'] = bb_df['lower']
        
        # ATR
        result['atr'] = TechnicalIndicators.atr(df)
        
        # Volume indicators
        result['obv'] = TechnicalIndicators.obv(df)
        result['vwap'] = TechnicalIndicators.vwap(df)
        
        # Returns and volatility
        result['returns'] = TechnicalIndicators.returns(df['close'])
        result['volatility'] = TechnicalIndicators.volatility(df['close'])
        
        # Momentum
        result['momentum_10'] = TechnicalIndicators.momentum(df['close'], 10)
        result['momentum_20'] = TechnicalIndicators.momentum(df['close'], 20)
        
        return result
