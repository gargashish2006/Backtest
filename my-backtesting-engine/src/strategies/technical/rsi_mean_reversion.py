"""
RSI Mean Reversion Strategy
Buy oversold stocks, sell overbought stocks using RSI indicator.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from ...strategies.base import Strategy


class RSIMeanReversion(Strategy):
    """
    Strategy: Buy when RSI < oversold_level, sell when RSI > overbought_level.
    
    Parameters:
        rsi_period (int): RSI calculation period (default: 14)
        oversold_level (float): RSI level to trigger buy (default: 30)
        overbought_level (float): RSI level to trigger sell (default: 70)
    """
    
    def __init__(self, rsi_period: int = 14, oversold_level: float = 30, overbought_level: float = 70):
        self.rsi_period = rsi_period
        self.oversold_level = oversold_level
        self.overbought_level = overbought_level
        self.name = f"RSI_{rsi_period}_MeanReversion_{int(oversold_level)}_{int(overbought_level)}"
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell signals based on RSI.
        
        Args:
            data: DataFrame with columns ['date', 'close'] at minimum
            
        Returns:
            DataFrame with added columns: 'rsi', 'signal', 'position'
        """
        df = data.copy()
        df = df.sort_values('date').reset_index(drop=True)
        
        # Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        # Generate signals
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold_level, 'signal'] = 1  # Oversold - Buy
        df.loc[df['rsi'] > self.overbought_level, 'signal'] = -1  # Overbought - Sell
        
        # Track position changes
        df['position'] = df['signal'].diff()
        
        return df
    
    def backtest(self, data: pd.DataFrame, initial_capital: float = 100000.0) -> Dict:
        """Run backtest with RSI mean reversion strategy."""
        df = self.generate_signals(data)
        df = df.dropna().reset_index(drop=True)
        
        if len(df) == 0:
            return self._empty_results()
        
        capital = initial_capital
        position = 0
        entry_price = 0
        shares = 0
        trades = []
        equity_curve = []
        
        for idx, row in df.iterrows():
            # Buy when RSI enters oversold
            if row['signal'] == 1 and position == 0:
                position = 1
                entry_price = row['close']
                shares = capital / entry_price
                trades.append({
                    'date': row['date'],
                    'type': 'BUY',
                    'price': entry_price,
                    'shares': shares,
                    'rsi': row['rsi'],
                    'capital': capital
                })
            
            # Sell when RSI enters overbought
            elif row['signal'] == -1 and position == 1:
                exit_price = row['close']
                pnl = (exit_price - entry_price) * shares
                capital += pnl
                
                trades.append({
                    'date': row['date'],
                    'type': 'SELL',
                    'price': exit_price,
                    'shares': shares,
                    'rsi': row['rsi'],
                    'pnl': pnl,
                    'capital': capital,
                    'return_pct': (pnl / (entry_price * shares)) * 100
                })
                
                position = 0
                shares = 0
            
            # Track equity
            current_equity = capital if position == 0 else shares * row['close']
            equity_curve.append({
                'date': row['date'],
                'equity': current_equity,
                'position': position,
                'rsi': row['rsi']
            })
        
        # Close final position
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
                'rsi': final_row['rsi'],
                'pnl': pnl,
                'capital': capital,
                'return_pct': (pnl / (entry_price * shares)) * 100
            })
        
        metrics = self._calculate_metrics(trades, equity_curve, initial_capital, capital)
        
        return {
            'strategy': self.name,
            'metrics': metrics,
            'trades': pd.DataFrame(trades),
            'equity_curve': pd.DataFrame(equity_curve),
            'signals': df
        }
    
    def _calculate_metrics(self, trades, equity_curve, initial_capital, final_capital):
        """Calculate performance metrics."""
        if len(trades) == 0:
            return self._empty_metrics()
        
        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_curve)
        sell_trades = trades_df[trades_df['type'].str.contains('SELL')]
        
        total_return = ((final_capital - initial_capital) / initial_capital) * 100
        num_trades = len(sell_trades)
        
        if num_trades == 0:
            return self._empty_metrics()
        
        winning_trades = sell_trades[sell_trades['pnl'] > 0]
        win_rate = (len(winning_trades) / num_trades) * 100
        avg_return = sell_trades['return_pct'].mean()
        
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
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
            'best_trade_pct': sell_trades['return_pct'].max(),
            'worst_trade_pct': sell_trades['return_pct'].min()
        }
    
    def _empty_results(self):
        return {
            'strategy': self.name,
            'metrics': self._empty_metrics(),
            'trades': pd.DataFrame(),
            'equity_curve': pd.DataFrame(),
            'signals': pd.DataFrame()
        }
    
    def _empty_metrics(self):
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
