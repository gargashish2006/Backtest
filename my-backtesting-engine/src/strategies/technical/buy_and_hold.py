
import pandas as pd
from typing import Dict
from ..base import Strategy

class BuyAndHold(Strategy):
    """
    Simple Buy and Hold strategy.
    Buys on the first available bar and holds until the end.
    """
    
    def __init__(self):
        self.name = "BuyAndHold"
    
    def generate_signals(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy signal on first day.
        """
        df = price_data.copy().sort_values('date').reset_index(drop=True)
        df['signal'] = 0
        
        if len(df) > 0:
            df.loc[0, 'signal'] = 1 # Buy on first day
            # Never sell (signal 0 means hold/do nothing)
            # To enforce holding, we don't need explicit hold signal if logic handles it.
            # But usually signal 1 = Buy, -1 = Sell.
            
        return df

    def backtest(self, price_data: pd.DataFrame, initial_capital: float = 100000.0) -> Dict:
        """
        Backtest buy and hold.
        """
        # Checks
        if len(price_data) == 0:
            return self._empty_results()

        df = self.generate_signals(price_data)
        
        # Simulation
        capital = initial_capital
        position = 0
        entry_price = 0
        shares = 0
        trades = []
        equity_curve = []
        
        for idx, row in df.iterrows():
            # Buy
            if row['signal'] == 1 and position == 0:
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
            
            # Update equity
            current_equity = capital if position == 0 else shares * row['close']
            equity_curve.append({
                'date': row['date'],
                'equity': current_equity
            })
            
        # Close at end
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
            
        return {
            'strategy': self.name,
            'metrics': {
                'total_return_pct': ((capital - initial_capital) / initial_capital) * 100,
                'final_capital': capital,
                'num_trades': 1
            },
            'trades': pd.DataFrame(trades),
            'equity_curve': pd.DataFrame(equity_curve),
            'signals': df
        }

    def _empty_results(self):
         return {
            'strategy': self.name,
            'metrics': {'total_return_pct': 0.0},
            'trades': pd.DataFrame(),
            'equity_curve': pd.DataFrame(),
            'signals': pd.DataFrame()
        }
