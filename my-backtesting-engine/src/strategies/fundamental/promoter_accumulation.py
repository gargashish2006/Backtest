"""
Promoter Accumulation Strategy
Buy when promoter holding increases significantly quarter-over-quarter.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from ...strategies.base import Strategy


class PromoterAccumulation(Strategy):
    """
    Strategy: Buy stocks where promoters are increasing their stake.
    
    Logic:
    - Buy when promoter holding increases by > threshold% QoQ
    - Hold for specified holding_period days
    - Track quarterly shareholding changes
    
    Parameters:
        min_increase_pct (float): Minimum promoter increase % to trigger buy (default: 1.0)
        min_promoter_holding (float): Minimum promoter holding % required (default: 40.0)
        holding_period (int): Days to hold after buying (default: 90)
    """
    
    def __init__(
        self, 
        min_increase_pct: float = 1.0,
        min_promoter_holding: float = 40.0,
        holding_period: int = 90
    ):
        self.min_increase_pct = min_increase_pct
        self.min_promoter_holding = min_promoter_holding
        self.holding_period = holding_period
        self.name = f"PromoterAccumulation_{min_increase_pct}pct_{holding_period}d"
    
    def generate_signals(
        self, 
        price_data: pd.DataFrame,
        shareholding_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Generate signals based on promoter holding changes.
        
        Args:
            price_data: Price OHLCV data
            shareholding_data: Shareholding pattern data with promoter_holding_pct
            
        Returns:
            DataFrame with signals merged into price data
        """
        # Ensure price data is sorted
        prices = price_data.copy().sort_values('date').reset_index(drop=True)
        
        # Sort shareholding by quarter
        shp = shareholding_data.copy()
        shp = shp.sort_values('quarter').reset_index(drop=True)
        
        # Calculate quarter-over-quarter change in promoter holding
        shp['promoter_change'] = shp['promoter_holding_pct'].diff()
        shp['promoter_change_pct'] = (shp['promoter_change'] / shp['promoter_holding_pct'].shift(1)) * 100
        
        # Identify buy signals
        buy_quarters = shp[
            (shp['promoter_change'] > self.min_increase_pct) &
            (shp['promoter_holding_pct'] >= self.min_promoter_holding)
        ].copy()
        
        # Convert quarters to approximate dates
        # Assuming quarter format is 'Mon-YYYY' like 'Dec-2025'
        buy_quarters['signal_date'] = pd.to_datetime(
            buy_quarters['quarter'], 
            format='%b-%Y',
            errors='coerce'
        )
        
        # Merge signals with price data
        prices['signal'] = 0
        prices['promoter_change'] = 0.0
        
        for _, signal_row in buy_quarters.iterrows():
            signal_date = signal_row['signal_date']
            if pd.notna(signal_date):
                # Find the first price date after signal_date
                mask = prices['date'] >= signal_date
                if mask.any():
                    first_idx = prices[mask].index[0]
                    prices.loc[first_idx, 'signal'] = 1
                    prices.loc[first_idx, 'promoter_change'] = signal_row['promoter_change']
        
        return prices
    
    def backtest(
        self, 
        price_data: pd.DataFrame,
        shareholding_data: pd.DataFrame,
        initial_capital: float = 100000.0
    ) -> Dict:
        """
        Run backtest based on promoter accumulation signals.
        
        Args:
            price_data: Price data for the stock
            shareholding_data: Shareholding data for the stock
            initial_capital: Starting capital
            
        Returns:
            Dictionary with backtest results
        """
        df = self.generate_signals(price_data, shareholding_data)
        
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
                    'promoter_change': row['promoter_change'],
                    'capital': capital
                })
            
            # Sell after holding period
            elif position == 1 and entry_date is not None:
                days_held = (row['date'] - entry_date).days
                
                if days_held >= self.holding_period:
                    exit_price = row['close']
                    pnl = (exit_price - entry_price) * shares
                    capital += pnl
                    
                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': exit_price,
                        'shares': shares,
                        'days_held': days_held,
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
                'position': position
            })
        
        # Close final position if open
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
