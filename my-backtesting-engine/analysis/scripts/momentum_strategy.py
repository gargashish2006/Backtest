"""
Momentum Strategy Backtest

Strategy:
- Universe: Top 100 stocks by market cap at signal time
- Signal: Monthly (at month-end)
- Ranking: Last 1-year returns
- Selection: Top 10 stocks by momentum
- Holding Period: 1 month (rebalance monthly)
- Position Management: Equal-weighted, net quantity execution
- Costs:
  - Transaction cost: 0.2% (buy and sell separately)
  - Impact cost: 1.0% (each transaction value)
- Tax:
  - Short-term (<1 year): 20% on gains
  - Long-term (>=1 year): 12.5% on gains
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sys
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class MomentumStrategy:
    """
    Momentum strategy that selects top 10 stocks from top 100 by market cap
    based on 1-year price momentum
    """
    
    def __init__(
        self,
        database_path: str = "database",
        initial_capital: float = 10_000_000,  # 1 Crore
        n_stocks_universe: int = 100,
        n_stocks_portfolio: int = 10,
        transaction_cost_pct: float = 0.2,
        impact_cost_pct: float = 1.0,
        short_term_tax_pct: float = 20.0,
        long_term_tax_pct: float = 12.5,
        long_term_days: int = 365
    ):
        """
        Initialize momentum strategy
        
        Args:
            database_path: Path to database directory
            initial_capital: Starting capital
            n_stocks_universe: Number of stocks in universe (top by market cap)
            n_stocks_portfolio: Number of stocks to hold
            transaction_cost_pct: Transaction cost percentage (applied separately to buy/sell)
            impact_cost_pct: Market impact cost percentage
            short_term_tax_pct: Tax rate for short-term gains (<1 year)
            long_term_tax_pct: Tax rate for long-term gains (>=1 year)
            long_term_days: Days threshold for long-term classification
        """
        self.database_path = Path(database_path)
        self.initial_capital = initial_capital
        self.n_stocks_universe = n_stocks_universe
        self.n_stocks_portfolio = n_stocks_portfolio
        self.transaction_cost_pct = transaction_cost_pct / 100
        self.impact_cost_pct = impact_cost_pct / 100
        self.short_term_tax_pct = short_term_tax_pct / 100
        self.long_term_tax_pct = long_term_tax_pct / 100
        self.long_term_days = long_term_days
        
        # Trading state
        self.current_holdings = {}  # {isin: {'qty': qty, 'avg_price': price, 'buy_date': date}}
        self.cash = initial_capital
        self.portfolio_value = initial_capital
        
        # Performance tracking
        self.trades = []
        self.daily_portfolio_values = []
        self.tax_paid = 0
        self.total_transaction_costs = 0
        self.total_impact_costs = 0
        
        # Tax loss harvesting
        self.tax_loss_carryforward = 0.0  # Accumulated losses to offset future gains
        self.total_tax_losses_generated = 0.0
        self.total_tax_losses_used = 0.0
        
        # Load data
        self._load_data()
        
    def _load_data(self):
        """Load price data and outstanding shares"""
        print("Loading data for momentum strategy...")
        
        # Load outstanding shares
        shares_file = self.database_path / "outstanding_shares.csv"
        if not shares_file.exists():
            raise FileNotFoundError(
                f"Outstanding shares file not found. Run: python scripts/create_outstanding_shares_file.py"
            )
        
        shares_df = pd.read_csv(shares_file)
        self.shares_lookup = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
        
        # Load price data in chunks with progress
        print("  Loading price data in chunks...")
        chunks = []
        chunksize = 500000
        chunk_count = 0
        
        for chunk in pd.read_csv(
            self.database_path / "price_data.csv",
            usecols=['isin', 'symbol', 'date', 'close'],
            dtype={'isin': 'category', 'symbol': 'category', 'close': 'float32'},
            parse_dates=['date'],
            chunksize=chunksize
        ):
            chunks.append(chunk)
            chunk_count += 1
            print(f"    Chunk {chunk_count} ({len(chunk):,} rows)...", end='\r')
        
        print(f"\n  Combining {chunk_count} chunks...")
        price_df = pd.concat(chunks, ignore_index=True)
        
        # Handle duplicates
        duplicates_count = price_df.duplicated(subset=['isin', 'date']).sum()
        if duplicates_count > 0:
            print(f"  Found {duplicates_count:,} duplicate records, keeping last value...")
            price_df = price_df.drop_duplicates(subset=['isin', 'date'], keep='last')
        
        # Map outstanding shares and calculate market cap
        price_df['shares'] = price_df['isin'].map(self.shares_lookup)
        price_df.dropna(subset=['shares'], inplace=True)
        price_df['market_cap'] = price_df['close'] * price_df['shares']
        
        # Sort by date and isin for efficient lookups
        price_df = price_df.sort_values(['date', 'isin'])
        
        # Create pivot table for fast price lookups
        print("  Creating optimized data structures...")
        self.price_pivot = price_df.pivot_table(
            index='date', 
            columns='isin', 
            values='close', 
            aggfunc='last'
        )
        
        self.mcap_pivot = price_df.pivot_table(
            index='date', 
            columns='isin', 
            values='market_cap', 
            aggfunc='last'
        )
        
        # Store symbol mapping
        symbol_map = price_df.groupby('isin')['symbol'].first()
        self.isin_to_symbol = symbol_map.to_dict()
        
        min_date = price_df['date'].min()
        max_date = price_df['date'].max()
        print(f"  Data loaded: {len(price_df):,} records from {min_date.date()} to {max_date.date()}")
        
    def _get_month_end_dates(self, start_date: str, end_date: str) -> List[pd.Timestamp]:
        """Get quarterly-end trading dates (Jan/Apr/Jul/Oct)"""
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Get all unique dates from pivot index
        all_dates = self.price_pivot.index
        all_dates = all_dates[(all_dates >= start) & (all_dates <= end)]
        
        # Find quarter-end dates (last trading day of Jan, Apr, Jul, Oct)
        quarter_ends = []
        target_months = [1, 4, 7, 10]  # Jan, Apr, Jul, Oct
        current_quarter = None
        
        for date in all_dates:
            if date.month in target_months:
                quarter_key = (date.year, date.month)
                if current_quarter != quarter_key:
                    if current_quarter is not None and last_date_of_quarter is not None:
                        quarter_ends.append(last_date_of_quarter)
                    current_quarter = quarter_key
                    last_date_of_quarter = date
                else:
                    last_date_of_quarter = date
        
        # Add the last date if it's in a target month
        if len(all_dates) > 0 and all_dates[-1].month in target_months:
            quarter_ends.append(all_dates[-1])
        
        return quarter_ends
    
    def _calculate_momentum(self, date: pd.Timestamp, lookback_days: int = 252) -> pd.DataFrame:
        """
        Calculate momentum for top N stocks by market cap (OPTIMIZED)
        
        Args:
            date: Current date
            lookback_days: Lookback period for momentum (252 = 1 year)
            
        Returns:
            DataFrame with top stocks ranked by momentum
        """
        # Get top N stocks by market cap on this date using pivot table
        if date not in self.mcap_pivot.index:
            return pd.DataFrame()
        
        mcap_series = self.mcap_pivot.loc[date].dropna()
        top_isins = mcap_series.nlargest(self.n_stocks_universe).index.tolist()
        
        if not top_isins:
            return pd.DataFrame()
        
        # Get current prices for top stocks
        current_prices = self.price_pivot.loc[date, top_isins].dropna()
        
        # Calculate lookback date
        lookback_date = date - pd.Timedelta(days=lookback_days)
        
        # Find the closest available date to lookback_date
        available_dates = self.price_pivot.index[self.price_pivot.index <= date]
        
        if len(available_dates) < 200:  # Need reasonable history
            return pd.DataFrame()
        
        # Get historical prices (from approximately lookback_days ago)
        hist_date_idx = max(0, len(available_dates) - lookback_days - 1)
        hist_date = available_dates[hist_date_idx]
        
        # Get historical prices for these stocks
        hist_prices = self.price_pivot.loc[hist_date, top_isins].dropna()
        
        # Calculate momentum only for stocks with both current and historical prices
        common_isins = current_prices.index.intersection(hist_prices.index)
        
        if len(common_isins) == 0:
            return pd.DataFrame()
        
        # Vectorized momentum calculation
        momentum = ((current_prices[common_isins] - hist_prices[common_isins]) / hist_prices[common_isins]) * 100
        
        # Create result DataFrame
        momentum_df = pd.DataFrame({
            'isin': common_isins,
            'current_price': current_prices[common_isins].values,
            'market_cap': mcap_series[common_isins].values,
            'momentum': momentum.values
        })
        
        # Add symbols
        momentum_df['symbol'] = momentum_df['isin'].map(self.isin_to_symbol)
        
        # Rank by momentum and select top N for portfolio
        momentum_df = momentum_df.sort_values('momentum', ascending=False)
        momentum_df = momentum_df.head(self.n_stocks_portfolio)
        
        # Calculate equal weights
        momentum_df['weight'] = 1.0 / len(momentum_df)
        
        return momentum_df
    
    def _execute_trades(
        self, 
        date: pd.Timestamp, 
        target_portfolio: pd.DataFrame
    ) -> None:
        """
        Execute trades to reach target portfolio
        
        Args:
            date: Trading date
            target_portfolio: DataFrame with target positions (isin, weight, current_price)
        """
        if target_portfolio.empty:
            return
        
        # Calculate current portfolio value (cash + holdings at current prices)
        # This ensures we use the total available capital for position sizing
        target_value = self._calculate_portfolio_value(date)
        
        target_positions = {}
        for _, row in target_portfolio.iterrows():
            isin = row['isin']
            weight = row['weight']
            price = row['current_price']
            
            # Target value for this position
            position_value = target_value * weight
            
            # Calculate quantity (considering costs)
            # Buy cost = price * (1 + transaction_cost + impact_cost)
            buy_cost_multiplier = 1 + self.transaction_cost_pct + self.impact_cost_pct
            qty = int(position_value / (price * buy_cost_multiplier))
            
            target_positions[isin] = {
                'qty': qty,
                'price': price,
                'symbol': row['symbol']
            }
        
        # Determine sells (positions not in target)
        for isin in list(self.current_holdings.keys()):
            if isin not in target_positions:
                # Sell entire position
                self._sell_position(date, isin, self.current_holdings[isin]['qty'])
        
        # Determine buys and adjustments
        for isin, target in target_positions.items():
            current_qty = self.current_holdings.get(isin, {}).get('qty', 0)
            target_qty = target['qty']
            price = target['price']
            
            qty_diff = target_qty - current_qty
            
            if qty_diff > 0:
                # Buy more
                self._buy_position(date, isin, qty_diff, price, target['symbol'])
            elif qty_diff < 0:
                # Sell some
                self._sell_position(date, isin, abs(qty_diff))
    
    def _buy_position(
        self, 
        date: pd.Timestamp, 
        isin: str, 
        qty: int, 
        price: float,
        symbol: str
    ) -> None:
        """Execute buy order"""
        if qty <= 0:
            return
        
        # Calculate costs
        gross_value = qty * price
        transaction_cost = gross_value * self.transaction_cost_pct
        impact_cost = gross_value * self.impact_cost_pct
        total_cost = gross_value + transaction_cost + impact_cost
        
        # Check if we have enough cash
        if total_cost > self.cash:
            # Reduce quantity to fit available cash
            available_for_purchase = self.cash / (price * (1 + self.transaction_cost_pct + self.impact_cost_pct))
            qty = int(available_for_purchase)
            
            if qty <= 0:
                return
            
            # Recalculate costs
            gross_value = qty * price
            transaction_cost = gross_value * self.transaction_cost_pct
            impact_cost = gross_value * self.impact_cost_pct
            total_cost = gross_value + transaction_cost + impact_cost
        
        # Execute buy
        self.cash -= total_cost
        self.total_transaction_costs += transaction_cost
        self.total_impact_costs += impact_cost
        
        # Update holdings
        if isin in self.current_holdings:
            # Average down/up
            old_qty = self.current_holdings[isin]['qty']
            old_avg_price = self.current_holdings[isin]['avg_price']
            new_qty = old_qty + qty
            new_avg_price = ((old_qty * old_avg_price) + gross_value) / new_qty
            
            self.current_holdings[isin]['qty'] = new_qty
            self.current_holdings[isin]['avg_price'] = new_avg_price
        else:
            self.current_holdings[isin] = {
                'qty': qty,
                'avg_price': price,
                'buy_date': date,
                'symbol': symbol
            }
        
        # Record trade
        self.trades.append({
            'date': date,
            'isin': isin,
            'symbol': symbol,
            'action': 'BUY',
            'qty': qty,
            'price': price,
            'gross_value': gross_value,
            'transaction_cost': transaction_cost,
            'impact_cost': impact_cost,
            'total_cost': total_cost,
            'tax': 0
        })
    
    def _sell_position(
        self, 
        date: pd.Timestamp, 
        isin: str, 
        qty: int
    ) -> None:
        """Execute sell order with tax calculation"""
        if isin not in self.current_holdings:
            return
        
        holding = self.current_holdings[isin]
        
        # Can't sell more than we have
        qty = min(qty, holding['qty'])
        
        if qty <= 0:
            return
        
        # Get current price from pivot table
        if date not in self.price_pivot.index or isin not in self.price_pivot.columns:
            return
        
        price = self.price_pivot.loc[date, isin]
        
        if pd.isna(price):
            return
        
        symbol = self.isin_to_symbol.get(isin, isin)
        
        # Calculate proceeds
        gross_value = qty * price
        transaction_cost = gross_value * self.transaction_cost_pct
        impact_cost = gross_value * self.impact_cost_pct
        net_proceeds = gross_value - transaction_cost - impact_cost
        
        # Calculate gain/loss
        cost_basis = qty * holding['avg_price']
        gain = gross_value - cost_basis
        holding_days = (date - holding['buy_date']).days
        
        # Calculate tax with loss carryforward
        tax = 0
        tax_loss_used = 0
        tax_loss_added = 0
        net_gain_after_offset = gain
        
        if gain < 0:
            # Loss: Add to carryforward for future use
            tax_loss_added = abs(gain)
            self.tax_loss_carryforward += abs(gain)
            self.total_tax_losses_generated += abs(gain)
        else:
            # Gain: First offset with carried forward losses
            if self.tax_loss_carryforward > 0:
                loss_to_use = min(self.tax_loss_carryforward, gain)
                tax_loss_used = loss_to_use
                self.tax_loss_carryforward -= loss_to_use
                self.total_tax_losses_used += loss_to_use
                net_gain_after_offset = gain - loss_to_use
            
            # Calculate tax on remaining gain (after loss offset)
            if net_gain_after_offset > 0:
                if holding_days >= self.long_term_days:
                    tax = net_gain_after_offset * self.long_term_tax_pct
                else:
                    tax = net_gain_after_offset * self.short_term_tax_pct
        
        # Update cash
        self.cash += net_proceeds - tax
        self.total_transaction_costs += transaction_cost
        self.total_impact_costs += impact_cost
        self.tax_paid += tax
        
        # Update holdings
        holding['qty'] -= qty
        
        if holding['qty'] <= 0:
            del self.current_holdings[isin]
        
        # Record trade
        self.trades.append({
            'date': date,
            'isin': isin,
            'symbol': symbol,
            'action': 'SELL',
            'qty': qty,
            'price': price,
            'gross_value': gross_value,
            'transaction_cost': transaction_cost,
            'impact_cost': impact_cost,
            'net_proceeds': net_proceeds,
            'cost_basis': cost_basis,
            'gain_loss': gain,
            'net_gain_after_offset': net_gain_after_offset,
            'tax_loss_used': tax_loss_used,
            'tax_loss_added': tax_loss_added,
            'tax': tax,
            'holding_days': holding_days,
            'tax_loss_carryforward': self.tax_loss_carryforward
        })
    
    def _calculate_portfolio_value(self, date: pd.Timestamp) -> float:
        """Calculate total portfolio value including cash (OPTIMIZED with forward-fill)"""
        holdings_value = 0
        
        if date not in self.price_pivot.index:
            return self.cash
        
        # Vectorized portfolio valuation with forward-fill for missing prices
        for isin, holding in self.current_holdings.items():
            if isin in self.price_pivot.columns:
                current_price = self.price_pivot.loc[date, isin]
                
                # If price is missing, use last known price (forward-fill)
                if pd.isna(current_price):
                    # Get all prices up to this date for this stock
                    historical_prices = self.price_pivot.loc[:date, isin]
                    # Get the last non-NaN price
                    last_known_price = historical_prices.dropna().iloc[-1] if len(historical_prices.dropna()) > 0 else None
                    if last_known_price is not None:
                        current_price = last_known_price
                
                if not pd.isna(current_price):
                    holdings_value += holding['qty'] * current_price
        
        return self.cash + holdings_value
    
    def run_backtest(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Run momentum strategy backtest
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with daily portfolio values
        """
        print(f"\nRunning Momentum Strategy Backtest...")
        print(f"Period: {start_date} to {end_date}")
        print(f"Universe: Top {self.n_stocks_universe} stocks by market cap")
        print(f"Portfolio: Top {self.n_stocks_portfolio} stocks by 1-year momentum")
        print(f"Rebalancing: Quarterly (Jan/Apr/Jul/Oct)")
        print(f"Initial Capital: ₹{self.initial_capital:,.0f}")
        print()
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # Get rebalance dates
        rebalance_dates = self._get_month_end_dates(start_date, end_date)
        print(f"Total rebalance dates: {len(rebalance_dates)}")
        
        # Get all trading days from pivot index
        all_dates = self.price_pivot.index
        all_dates = all_dates[(all_dates >= start) & (all_dates <= end)]
        
        # Run backtest
        rebalance_idx = 0
        rebalance_count = 0
        
        for i, date in enumerate(all_dates):
            # Check if rebalance needed
            is_rebalance = (rebalance_idx < len(rebalance_dates) and 
                           date >= rebalance_dates[rebalance_idx])
            
            if is_rebalance:
                # Calculate momentum and get target portfolio
                target_portfolio = self._calculate_momentum(date)
                
                # Execute trades
                self._execute_trades(date, target_portfolio)
                
                rebalance_idx += 1
                rebalance_count += 1
                
                if rebalance_count % 4 == 0:  # Print every year (4 quarters)
                    holdings_str = ', '.join([f"{h['symbol']}" for h in list(self.current_holdings.values())[:5]])
                    if len(self.current_holdings) > 5:
                        holdings_str += f"... ({len(self.current_holdings)} total)"
                    print(f"  {date.date()}: Portfolio value: ₹{self.portfolio_value:,.0f} | Holdings: {holdings_str}")
            
            # Calculate portfolio value
            self.portfolio_value = self._calculate_portfolio_value(date)
            
            # Record daily value
            self.daily_portfolio_values.append({
                'date': date,
                'portfolio_value': self.portfolio_value,
                'cash': self.cash,
                'num_holdings': len(self.current_holdings)
            })
            
            # Progress indicator
            if i % 250 == 0 or i == len(all_dates) - 1:
                sys.stdout.write(f"\rProgress: {i+1}/{len(all_dates)} days")
                sys.stdout.flush()
        
        print("\n")
        
        # Create results DataFrame
        results = pd.DataFrame(self.daily_portfolio_values)
        
        # Calculate returns
        results['daily_return'] = results['portfolio_value'].pct_change()
        results['cumulative_return'] = (results['portfolio_value'] / self.initial_capital - 1) * 100
        
        return results
    
    def get_performance_stats(self, results: pd.DataFrame) -> Dict:
        """Calculate performance statistics"""
        final_value = results.iloc[-1]['portfolio_value']
        total_return = (final_value / self.initial_capital - 1) * 100
        
        # Calculate CAGR
        days = (results['date'].max() - results['date'].min()).days
        cagr = (((final_value / self.initial_capital) ** (365.25 / days)) - 1) * 100
        
        # Volatility
        daily_returns = results['daily_return'].dropna()
        volatility = daily_returns.std() * (252 ** 0.5) * 100
        
        # Max drawdown
        running_max = results['portfolio_value'].expanding().max()
        drawdown = ((results['portfolio_value'] - running_max) / running_max) * 100
        max_drawdown = drawdown.min()
        
        # Sharpe ratio
        sharpe = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
        
        # Trade statistics
        trades_df = pd.DataFrame(self.trades)
        num_trades = len(trades_df)
        
        if not trades_df.empty:
            buy_trades = trades_df[trades_df['action'] == 'BUY']
            sell_trades = trades_df[trades_df['action'] == 'SELL']
            
            winning_trades = sell_trades[sell_trades['gain_loss'] > 0]
            win_rate = (len(winning_trades) / len(sell_trades) * 100) if len(sell_trades) > 0 else 0
            
            avg_gain = winning_trades['gain_loss'].mean() if len(winning_trades) > 0 else 0
            losing_trades = sell_trades[sell_trades['gain_loss'] <= 0]
            avg_loss = losing_trades['gain_loss'].mean() if len(losing_trades) > 0 else 0
        else:
            win_rate = 0
            avg_gain = 0
            avg_loss = 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'cagr': cagr,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'avg_gain': avg_gain,
            'avg_loss': avg_loss,
            'total_transaction_costs': self.total_transaction_costs,
            'total_impact_costs': self.total_impact_costs,
            'tax_paid': self.tax_paid,
            'tax_losses_generated': self.total_tax_losses_generated,
            'tax_losses_used': self.total_tax_losses_used,
            'tax_loss_carryforward': self.tax_loss_carryforward
        }


def run_momentum_backtest(
    start_date: str = "2016-02-01",
    end_date: str = "2026-01-28",
    initial_capital: float = 10_000_000,
    output_dir: str = "analysis/outputs/strategies"
) -> pd.DataFrame:
    """
    Run momentum strategy backtest
    
    Args:
        start_date: Start date
        end_date: End date
        initial_capital: Starting capital
        output_dir: Output directory for results
        
    Returns:
        Results DataFrame
    """
    # Create strategy instance
    strategy = MomentumStrategy(
        initial_capital=initial_capital,
        n_stocks_universe=100,
        n_stocks_portfolio=10,
        transaction_cost_pct=0.2,
        impact_cost_pct=1.0,
        short_term_tax_pct=20.0,
        long_term_tax_pct=12.5
    )
    
    # Run backtest
    results = strategy.run_backtest(start_date, end_date)
    
    # Get performance stats
    stats = strategy.get_performance_stats(results)
    
    # Print results
    print("=" * 80)
    print("MOMENTUM STRATEGY PERFORMANCE")
    print("=" * 80)
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Capital: ₹{stats['initial_capital']:,.0f}")
    print(f"Final Value: ₹{stats['final_value']:,.0f}")
    print(f"Total Return: {stats['total_return']:.2f}%")
    print(f"CAGR: {stats['cagr']:.2f}%")
    print(f"Volatility: {stats['volatility']:.2f}%")
    print(f"Max Drawdown: {stats['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
    print()
    print("TRADE STATISTICS:")
    print(f"Total Trades: {stats['num_trades']}")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Avg Gain: ₹{stats['avg_gain']:,.0f}")
    print(f"Avg Loss: ₹{stats['avg_loss']:,.0f}")
    print()
    print("COSTS:")
    print(f"Transaction Costs: ₹{stats['total_transaction_costs']:,.0f}")
    print(f"Impact Costs: ₹{stats['total_impact_costs']:,.0f}")
    print(f"Tax Paid (20% ST / 12.5% LT): ₹{stats['tax_paid']:,.0f}")
    print()
    print("TAX LOSS HARVESTING:")
    print(f"Tax Losses Generated: ₹{stats['tax_losses_generated']:,.0f}")
    print(f"Tax Losses Used to Offset Gains: ₹{stats['tax_losses_used']:,.0f}")
    print(f"Tax Loss Carryforward (Unused): ₹{stats['tax_loss_carryforward']:,.0f}")
    print(f"Tax Saved from Loss Harvesting: ₹{stats['tax_losses_used'] * 0.20:,.0f} (approx @ 20%)")
    print()
    print(f"Total Costs: ₹{stats['total_transaction_costs'] + stats['total_impact_costs'] + stats['tax_paid']:,.0f}")
    print("=" * 80)
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results_file = output_path / f"momentum_strategy_{start_date}_to_{end_date}.csv"
    results.to_csv(results_file, index=False)
    print(f"\nResults saved to: {results_file}")
    
    # Save trades
    trades_df = pd.DataFrame(strategy.trades)
    trades_file = output_path / f"momentum_trades_{start_date}_to_{end_date}.csv"
    trades_df.to_csv(trades_file, index=False)
    print(f"Trades saved to: {trades_file}")
    
    # Save stats
    stats_df = pd.DataFrame([stats])
    stats_file = output_path / f"momentum_stats_{start_date}_to_{end_date}.csv"
    stats_df.to_csv(stats_file, index=False)
    print(f"Stats saved to: {stats_file}")
    
    return results, strategy


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Momentum Strategy Backtest")
    parser.add_argument("--start-date", default="2016-02-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-01-28", help="End date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=10_000_000, help="Initial capital")
    parser.add_argument("--output-dir", default="analysis/outputs/strategies", help="Output directory")
    
    args = parser.parse_args()
    
    run_momentum_backtest(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.capital,
        output_dir=args.output_dir
    )
