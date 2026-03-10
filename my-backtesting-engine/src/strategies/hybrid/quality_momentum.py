"""
Quality Momentum Strategy
Combines high promoter holding (quality) with price momentum (technical).
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from ...strategies.base import Strategy


class QualityMomentum(Strategy):
    """
    Strategy: Buy stocks with high promoter holding AND strong price momentum.
    
    Logic:
    - Filter stocks with promoter holding > min_promoter_pct
    - Buy when price momentum (returns over lookback period) > min_momentum_pct
    - Sell when momentum turns negative or after max_holding_days
    
    Parameters:
        min_promoter_pct (float): Minimum promoter holding % (default: 50.0)
        lookback_days (int): Momentum calculation period (default: 60)
        min_momentum_pct (float): Minimum momentum % to buy (default: 10.0)
        max_holding_days (int): Maximum days to hold (default: 180)
    """
    
    def __init__(
        self,
        min_promoter_pct: float = 50.0,
        lookback_days: int = 60,
        min_momentum_pct: float = 10.0,
        max_holding_days: int = 180
    ):
        self.min_promoter_pct = min_promoter_pct
        self.lookback_days = lookback_days
        self.min_momentum_pct = min_momentum_pct
        self.max_holding_days = max_holding_days
        self.name = f"QualityMomentum_{int(min_promoter_pct)}P_{lookback_days}D_{int(min_momentum_pct)}M"
    
    def calculate_momentum(self, prices: pd.Series, lookback: int) -> pd.Series:
        """Calculate price momentum (% return over lookback period)."""
        return ((prices / prices.shift(lookback)) - 1) * 100
    
    def generate_signals(
        self,
        price_data: pd.DataFrame,
        shareholding_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Generate signals combining promoter holding and momentum.
        
        Args:
            price_data: Price OHLCV data
            shareholding_data: Shareholding patterns with promoter_holding_pct
            
        Returns:
            DataFrame with signals
        """
        df = price_data.copy().sort_values('date').reset_index(drop=True)
        
        # Calculate momentum
        df['momentum'] = self.calculate_momentum(df['close'], self.lookback_days)
        
        # Get latest promoter holding
        if len(shareholding_data) > 0:
            latest_holding = shareholding_data.sort_values('quarter').iloc[-1]['promoter_holding_pct']
        else:
            latest_holding = 0.0
        
        df['promoter_holding'] = latest_holding
        
        # Generate signals
        # Buy: High promoter holding AND strong momentum
        df['signal'] = 0
        df.loc[
            (df['promoter_holding'] >= self.min_promoter_pct) &
            (df['momentum'] >= self.min_momentum_pct),
            'signal'
        ] = 1
        
        # Sell: Momentum turns negative
        df.loc[df['momentum'] < 0, 'signal'] = -1
        
        return df
    
    def backtest(
        self,
        price_data: pd.DataFrame,
        shareholding_data: pd.DataFrame,
        initial_capital: float = 100000.0
    ) -> Dict:
        """Run backtest with quality momentum strategy."""
        df = self.generate_signals(price_data, shareholding_data)
        df = df.dropna().reset_index(drop=True)
        
        if len(df) == 0:
            return self._empty_results()
        
        capital = initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        shares = 0
        trades = []
        equity_curve = []
        
        for idx, row in df.iterrows():
            # Buy signal
            if row['signal'] == 1 and position == 0:
                position = 1
                entry_price = row['close']
                entry_date = row['date']
                shares = capital / entry_price
                
                trades.append({
                    'date': row['date'],
                    'type': 'BUY',
                    'price': entry_price,
                    'shares': shares,
                    'momentum': row['momentum'],
                    'promoter_holding': row['promoter_holding'],
                    'capital': capital
                })
            
            # Sell signal or max holding period reached
            elif position == 1:
                days_held = (row['date'] - entry_date).days
                should_sell = (row['signal'] == -1) or (days_held >= self.max_holding_days)
                
                if should_sell:
                    exit_price = row['close']
                    pnl = (exit_price - entry_price) * shares
                    capital += pnl
                    
                    sell_reason = 'MAX_HOLD' if days_held >= self.max_holding_days else 'MOMENTUM_NEGATIVE'
                    
                    trades.append({
                        'date': row['date'],
                        'type': f'SELL ({sell_reason})',
                        'price': exit_price,
                        'shares': shares,
                        'days_held': days_held,
                        'momentum': row['momentum'],
                        'pnl': pnl,
                        'capital': capital,
                        'return_pct': (pnl / (entry_price * shares)) * 100
                    })
                    
                    position = 0
                    shares = 0
                    entry_date = None
            
            # Track equity
            current_equity = capital if position == 0 else shares * row['close']
            equity_curve.append({
                'date': row['date'],
                'equity': current_equity,
                'position': position,
                'momentum': row['momentum']
            })
        
        # Close final position
        if position == 1:
            final_row = df.iloc[-1]
            exit_price = final_row['close']
            pnl = (exit_price - entry_price) * shares
            capital += pnl
            days_held = (final_row['date'] - entry_date).days
            
            trades.append({
                'date': final_row['date'],
                'type': 'SELL (CLOSE)',
                'price': exit_price,
                'shares': shares,
                'days_held': days_held,
                'momentum': final_row['momentum'],
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
        avg_holding_days = sell_trades['days_held'].mean() if 'days_held' in sell_trades else 0
        
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
            'avg_holding_days': avg_holding_days,
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
            'avg_holding_days': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': 0.0,
            'best_trade_pct': 0.0,
            'worst_trade_pct': 0.0
        }
