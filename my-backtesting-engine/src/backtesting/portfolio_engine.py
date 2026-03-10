"""
Portfolio-Based Backtesting Engine
Integrates strategies with portfolio management system.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from .portfolio_manager import Portfolio
from .config import BacktestConfig


class PortfolioBacktestEngine:
    """
    Advanced backtesting engine that runs strategies with realistic portfolio management.
    
    Features:
    - Multiple concurrent positions with max limits
    - Equal weight capital allocation
    - Transaction and impact costs
    - Short-term and long-term tax calculations
    - Position-based entry/exit
    - Complete trade logging
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtest configuration (capital, max positions, costs)
        """
        self.config = config
        self.portfolio = Portfolio(config)
        
    def run_strategy_single_stock(
        self, 
        strategy,
        stock_data: pd.DataFrame,
        isin: str,
        symbol: str,
        exchange: str,
        company_name: str = ""
    ) -> Dict:
        """
        Run a strategy on a single stock (for testing/validation).
        
        Args:
            strategy: Strategy object with generate_signals() method
            stock_data: DataFrame with price data (date, open, high, low, close, volume)
            isin: Stock ISIN
            symbol: Trading symbol
            exchange: Exchange (NSE/BSE)
            company_name: Company name for display
            
        Returns:
            Dictionary with backtest results
        """
        if stock_data is None or len(stock_data) == 0:
            return self._empty_results(strategy.name, isin)
        
        # Generate signals
        signals_df = strategy.generate_signals(stock_data)
        
        if len(signals_df) == 0:
            return self._empty_results(strategy.name, isin)
        
        # Run through signals day by day
        for idx, row in signals_df.iterrows():
            date = row['date']
            price = row['close']
            
            # Check if we have an open position
            has_position = isin in self.portfolio.open_positions
            
            # SELL signal and we have position
            if row.get('position', 0) == -2 and has_position:
                self.portfolio.close_position(isin, price, date)
            
            # BUY signal and we don't have position
            elif row.get('position', 0) == 2 and not has_position:
                # Check if we can open new position
                if self.portfolio.can_open_new_position:
                    self.portfolio.open_position(
                        isin=isin,
                        symbol=symbol,
                        exchange=exchange,
                        price=price,
                        date=date
                    )
            
            # Update all positions with current prices
            self.portfolio.update_positions({isin: price}, date)
            self.portfolio.record_state(date)
        
        # Close any remaining open positions at end
        if isin in self.portfolio.open_positions:
            final_price = signals_df.iloc[-1]['close']
            final_date = signals_df.iloc[-1]['date']
            self.portfolio.close_position(isin, final_price, final_date)
        
        # Get results
        summary = self.portfolio.get_summary()
        
        return {
            'strategy': strategy.name,
            'stock': company_name or symbol,
            'isin': isin,
            'symbol': symbol,
            'period': {
                'start': signals_df.iloc[0]['date'],
                'end': signals_df.iloc[-1]['date'],
                'days': len(signals_df)
            },
            'performance': summary,
            'trades': pd.DataFrame(self.portfolio.trade_log),
            'equity_curve': pd.DataFrame(self.portfolio.history),
            'signals': signals_df
        }
    
    def run_strategy_multi_stock(
        self,
        strategy,
        stocks_data: Dict[str, Dict],
        rebalance_frequency: str = 'daily'
    ) -> Dict:
        """
        Run a strategy across multiple stocks with portfolio management.
        
        Args:
            strategy: Strategy object with generate_signals() method
            stocks_data: Dictionary mapping ISIN to stock data dict containing:
                - 'data': DataFrame with price data
                - 'symbol': Trading symbol
                - 'exchange': Exchange (NSE/BSE)
                - 'company_name': Company name
            rebalance_frequency: 'daily', 'weekly', or 'monthly'
            
        Returns:
            Dictionary with consolidated backtest results
        """
        print(f"\n{'='*80}")
        print(f"Running Portfolio Backtest: {strategy.name}")
        print(f"Universe: {len(stocks_data)} stocks")
        print(f"Max Positions: {self.config.MAX_POSITIONS}")
        print(f"Initial Capital: ₹{self.config.INITIAL_CAPITAL:,.0f}")
        print(f"{'='*80}\n")
        
        # Generate signals for all stocks
        all_signals = {}
        valid_stocks = []
        
        for isin, stock_info in stocks_data.items():
            stock_data = stock_info['data']
            if stock_data is None or len(stock_data) == 0:
                continue
            
            # Generate signals
            signals_df = strategy.generate_signals(stock_data)
            if len(signals_df) > 0:
                all_signals[isin] = signals_df
                valid_stocks.append(isin)
        
        if len(valid_stocks) == 0:
            return self._empty_results(strategy.name, "Multi-Stock")
        
        print(f"Generated signals for {len(valid_stocks)} stocks\n")
        
        # Get all unique dates across all stocks
        all_dates = set()
        for signals_df in all_signals.values():
            all_dates.update(signals_df['date'].unique())
        all_dates = sorted(list(all_dates))
        
        # Create price matrix for efficient lookup
        price_matrix = {}
        for isin, signals_df in all_signals.items():
            price_dict = dict(zip(signals_df['date'], signals_df['close']))
            price_matrix[isin] = price_dict
        
        # Run through each trading day
        trades_count = 0
        for date_idx, date in enumerate(all_dates):
            # Collect all signals for this date
            sell_signals = []
            buy_signals = []
            current_prices = {}
            
            for isin in valid_stocks:
                if date not in all_signals[isin]['date'].values:
                    continue
                
                row = all_signals[isin][all_signals[isin]['date'] == date].iloc[0]
                price = row['close']
                current_prices[isin] = price
                
                # Collect signals
                if row.get('position', 0) == -2:  # Sell signal
                    sell_signals.append((isin, price))
                elif row.get('position', 0) == 2:  # Buy signal
                    buy_signals.append((isin, price))
            
            # Process SELL signals first (free up capital)
            for isin, price in sell_signals:
                if isin in self.portfolio.open_positions:
                    self.portfolio.close_position(isin, price, date)
                    trades_count += 1
            
            # Process BUY signals (use freed capital)
            for isin, price in buy_signals:
                # Skip if already have position
                if isin in self.portfolio.open_positions:
                    continue
                
                # Check if we can open new position
                if self.portfolio.can_open_new_position:
                    stock_info = stocks_data[isin]
                    self.portfolio.open_position(
                        isin=isin,
                        symbol=stock_info['symbol'],
                        exchange=stock_info['exchange'],
                        price=price,
                        date=date
                    )
                    trades_count += 1
            
            # Update all open positions with current prices
            if len(current_prices) > 0:
                self.portfolio.update_positions(current_prices, date)
            
            # Record portfolio state
            self.portfolio.record_state(date)
            
            # Progress update every 100 days
            if (date_idx + 1) % 100 == 0 or date_idx == len(all_dates) - 1:
                progress = (date_idx + 1) / len(all_dates) * 100
                print(f"Progress: {progress:.1f}% | Date: {date.strftime('%Y-%m-%d')} | "
                      f"Open Positions: {self.portfolio.num_open_positions} | "
                      f"Capital: ₹{self.portfolio.total_capital:,.0f} | "
                      f"Trades: {trades_count}")
        
        # Close all remaining positions at end
        final_date = all_dates[-1]
        for isin in list(self.portfolio.open_positions.keys()):
            if isin in price_matrix and final_date in price_matrix[isin]:
                final_price = price_matrix[isin][final_date]
                self.portfolio.close_position(isin, final_price, final_date)
                trades_count += 1
        
        # Get results
        summary = self.portfolio.get_summary()
        
        print(f"\n{'='*80}")
        print(f"Backtest Complete!")
        print(f"Total Return: {summary['total_return_pct']:.2f}%")
        print(f"Total Trades: {summary['total_trades']}")
        print(f"Win Rate: {summary['win_rate']:.1f}%")
        print(f"Tax Paid: ₹{summary['total_tax_paid']:,.2f}")
        print(f"Costs Paid: ₹{summary['total_costs_paid']:,.2f}")
        print(f"{'='*80}\n")
        
        return {
            'strategy': strategy.name,
            'universe_size': len(stocks_data),
            'valid_stocks': len(valid_stocks),
            'period': {
                'start': all_dates[0],
                'end': all_dates[-1],
                'days': len(all_dates)
            },
            'performance': summary,
            'trades': pd.DataFrame(self.portfolio.trade_log),
            'equity_curve': pd.DataFrame(self.portfolio.history),
            'config': {
                'initial_capital': self.config.INITIAL_CAPITAL,
                'max_positions': self.config.MAX_POSITIONS,
                'transaction_cost': self.config.costs.TRANSACTION_COST_BUY,
                'impact_cost': self.config.costs.IMPACT_COST_BUY,
                'short_term_tax': self.config.costs.SHORT_TERM_TAX_RATE,
                'long_term_tax': self.config.costs.LONG_TERM_TAX_RATE
            }
        }
    
    def _empty_results(self, strategy_name: str, identifier: str) -> Dict:
        """Return empty results when no data available."""
        return {
            'strategy': strategy_name,
            'stock': identifier,
            'error': 'No data available',
            'performance': self.portfolio.get_summary(),
            'trades': pd.DataFrame(),
            'equity_curve': pd.DataFrame(),
            'signals': pd.DataFrame()
        }
    
    def reset(self):
        """Reset portfolio for new backtest."""
        self.portfolio = Portfolio(self.config)


def run_backtest_comparison(
    strategies: List,
    stocks_data: Dict[str, Dict],
    configs: List[BacktestConfig]
) -> pd.DataFrame:
    """
    Run multiple strategies with different configurations and compare results.
    
    Args:
        strategies: List of strategy objects to test
        stocks_data: Dictionary mapping ISIN to stock data
        configs: List of BacktestConfig objects (e.g., different max positions)
        
    Returns:
        DataFrame comparing all strategy/config combinations
    """
    results = []
    
    for strategy in strategies:
        for config in configs:
            print(f"\n{'#'*80}")
            print(f"Testing: {strategy.name} with {config.MAX_POSITIONS} max positions")
            print(f"{'#'*80}")
            
            # Create engine
            engine = PortfolioBacktestEngine(config)
            
            # Run backtest
            result = engine.run_strategy_multi_stock(
                strategy=strategy,
                stocks_data=stocks_data
            )
            
            # Extract key metrics
            perf = result['performance']
            results.append({
                'strategy': strategy.name,
                'max_positions': config.MAX_POSITIONS,
                'initial_capital': config.INITIAL_CAPITAL,
                'final_capital': perf['final_capital'],
                'total_return_pct': perf['total_return_pct'],
                'total_trades': perf['total_trades'],
                'winning_trades': perf['winning_trades'],
                'losing_trades': perf['losing_trades'],
                'win_rate': perf['win_rate'],
                'avg_win': perf['avg_win'],
                'avg_loss': perf['avg_loss'],
                'profit_factor': perf['profit_factor'],
                'total_tax_paid': perf['total_tax_paid'],
                'total_costs_paid': perf['total_costs_paid'],
                'net_after_costs': perf['final_capital'] - perf['total_tax_paid'] - perf['total_costs_paid']
            })
    
    return pd.DataFrame(results)
