"""
Moving Average Crossover Strategy
Classic trend-following strategy using MA crossovers.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from ...strategies.base import Strategy


class MovingAverageCrossover(Strategy):
    """
    Strategy: Buy when fast MA crosses above slow MA, sell when it crosses below.
    
    Parameters:
        fast_period (int): Fast moving average period (default: 20)
        slow_period (int): Slow moving average period (default: 50)
        ma_type (str): 'SMA' or 'EMA' (default: 'SMA')
    """
    
    def __init__(self, fast_period: int = 20, slow_period: int = 50, ma_type: str = 'SMA'):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.ma_type = ma_type
        self.name = f"MA_{fast_period}_{slow_period}_Crossover_{ma_type}"
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell signals based on MA crossover.
        
        Args:
            data: DataFrame with columns ['date', 'close'] at minimum
            
        Returns:
            DataFrame with added columns: 'fast_ma', 'slow_ma', 'signal', 'position'
        """
        df = data.copy()
        df = df.sort_values('date').reset_index(drop=True)
        
        # Calculate moving averages
        if self.ma_type == 'SMA':
            df['fast_ma'] = df['close'].rolling(window=self.fast_period).mean()
            df['slow_ma'] = df['close'].rolling(window=self.slow_period).mean()
        else:  # EMA
            df['fast_ma'] = df['close'].ewm(span=self.fast_period, adjust=False).mean()
            df['slow_ma'] = df['close'].ewm(span=self.slow_period, adjust=False).mean()
        
        # Generate signals
        # 1 = Buy, -1 = Sell, 0 = Hold
        df['signal'] = 0
        df.loc[df['fast_ma'] > df['slow_ma'], 'signal'] = 1
        df.loc[df['fast_ma'] < df['slow_ma'], 'signal'] = -1
        
        # Detect crossovers (signal changes)
        df['position'] = df['signal'].diff()
        # position: 2 = bullish crossover (buy), -2 = bearish crossover (sell)
        
        return df
    
    def backtest(self, data: pd.DataFrame, initial_capital: float = 100000.0) -> Dict:
        """
        Run backtest on the data.
        
        Args:
            data: Price data DataFrame
            initial_capital: Starting capital
            
        Returns:
            Dictionary with backtest results and metrics
        """
        df = self.generate_signals(data)
        
        # Remove NaN rows (initial periods where MA can't be calculated)
        df = df.dropna().reset_index(drop=True)
        
        if len(df) == 0:
            return self._empty_results()
        
        # Initialize tracking
        capital = initial_capital
        position = 0  # 0 = no position, 1 = long position
        entry_price = 0
        trades = []
        equity_curve = []
        
        for idx, row in df.iterrows():
            # Buy signal: fast MA crosses above slow MA
            if row['position'] == 2 and position == 0:
                position = 1
                entry_price = row['close']
                shares = capital / entry_price
                trades.append({
                    'date': row['date'],
                    'type': 'BUY',
                    'price': entry_price,
                    'shares': shares,
                    'capital': capital
                })
            
            # Sell signal: fast MA crosses below slow MA
            elif row['position'] == -2 and position == 1:
                exit_price = row['close']
                pnl = (exit_price - entry_price) * shares
                capital += pnl
                
                trades.append({
                    'date': row['date'],
                    'type': 'SELL',
                    'price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'capital': capital,
                    'return_pct': (pnl / (entry_price * shares)) * 100
                })
                
                position = 0
                shares = 0
            
            # Calculate current equity
            current_equity = capital
            if position == 1:
                current_equity = shares * row['close']
            
            equity_curve.append({
                'date': row['date'],
                'equity': current_equity,
                'position': position
            })
        
        # Close any open position at the end
        if position == 1:
            final_row = df.iloc[-1]
            exit_price = final_row['close']
            pnl = (exit_price - entry_price) * shares
            capital += pnl
            
            trades.append({
                'date': final_row['date'],
                'type': 'SELL (CLOSE)',
                'price': exit_price,
                'shares': shares,
                'pnl': pnl,
                'capital': capital,
                'return_pct': (pnl / (entry_price * shares)) * 100
            })
        
        # Calculate metrics
        metrics = self._calculate_metrics(
            trades, 
            equity_curve, 
            initial_capital, 
            capital
        )
        
        return {
            'strategy': self.name,
            'metrics': metrics,
            'trades': pd.DataFrame(trades),
            'equity_curve': pd.DataFrame(equity_curve),
            'signals': df
        }
    
    def _calculate_metrics(
        self, 
        trades: List[Dict], 
        equity_curve: List[Dict],
        initial_capital: float,
        final_capital: float
    ) -> Dict:
        """Calculate performance metrics."""
        
        if len(trades) == 0:
            return self._empty_metrics()
        
        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_curve)
        
        # Filter sell trades for returns
        sell_trades = trades_df[trades_df['type'].str.contains('SELL')]
        
        # Basic metrics
        total_return = ((final_capital - initial_capital) / initial_capital) * 100
        num_trades = len(sell_trades)
        
        if num_trades == 0:
            return {
                'total_return_pct': 0.0,
                'num_trades': 0,
                'win_rate': 0.0,
                'avg_return_per_trade': 0.0,
                'max_drawdown_pct': 0.0,
                'sharpe_ratio': 0.0
            }
        
        # Win rate
        winning_trades = sell_trades[sell_trades['pnl'] > 0]
        win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
        
        # Average return per trade
        avg_return = sell_trades['return_pct'].mean() if num_trades > 0 else 0
        
        # Max drawdown
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # Sharpe ratio (simplified - assuming daily returns)
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe = (equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252)) if equity_df['returns'].std() > 0 else 0
        
        return {
            'total_return_pct': total_return,
            'final_capital': final_capital,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'avg_return_per_trade': avg_return,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'best_trade_pct': sell_trades['return_pct'].max() if num_trades > 0 else 0,
            'worst_trade_pct': sell_trades['return_pct'].min() if num_trades > 0 else 0
        }
    
    def _empty_results(self) -> Dict:
        """Return empty results structure."""
        return {
            'strategy': self.name,
            'metrics': self._empty_metrics(),
            'trades': pd.DataFrame(),
            'equity_curve': pd.DataFrame(),
            'signals': pd.DataFrame()
        }
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics."""
        return {
            'total_return_pct': 0.0,
            'final_capital': 0.0,
            'num_trades': 0,
            'win_rate': 0.0,
            'avg_return_per_trade': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': 0.0,
            'best_trade_pct': 0.0,
            'worst_trade_pct': 0.0
        }
