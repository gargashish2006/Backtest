"""
Quick Test: Portfolio Backtest on Single Stock
Test the portfolio system with a simple example.
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backtesting.config import BacktestConfig
from src.backtesting.portfolio_engine import PortfolioBacktestEngine
from src.strategies.technical.moving_average_crossover import MovingAverageCrossover


def main():
    print("="*80)
    print("PORTFOLIO BACKTEST - QUICK TEST")
    print("="*80)
    print()
    
    # Load sample stock data
    print("Loading stock data...")
    db_path = Path("database")
    
    # Load master identifiers to get a stock
    master_df = pd.read_csv(db_path / "master_identifiers.csv")
    
    # Get first NSE stock as example
    sample_stock = master_df[master_df['primary_exchange'] == 'NSE'].iloc[0]
    isin = sample_stock['isin']
    symbol = sample_stock['primary_symbol']
    company_name = sample_stock['company_name']
    
    print(f"Stock: {company_name}")
    print(f"Symbol: {symbol}")
    print(f"ISIN: {isin}")
    print()
    
    # Load price data for this stock
    price_df = pd.read_csv(db_path / "price_data.csv")
    stock_prices = price_df[price_df['isin'] == isin].copy()
    
    if len(stock_prices) == 0:
        print("Error: No price data found for this stock")
        return
    
    # Convert date and sort
    stock_prices['date'] = pd.to_datetime(stock_prices['date'])
    stock_prices = stock_prices.sort_values('date').reset_index(drop=True)
    
    print(f"Price data: {len(stock_prices)} days")
    print(f"Period: {stock_prices['date'].min()} to {stock_prices['date'].max()}")
    print()
    
    # Create configuration
    config = BacktestConfig(
        INITIAL_CAPITAL=100000,  # ₹1 Lakh
        MAX_POSITIONS=1          # Single stock test
    )
    
    print("Configuration:")
    print(f"  Initial Capital: ₹{config.INITIAL_CAPITAL:,.0f}")
    print(f"  Transaction Cost: {config.costs.TRANSACTION_COST_BUY*100:.2f}%")
    print(f"  Impact Cost: {config.costs.IMPACT_COST_BUY*100:.2f}%")
    print(f"  Short-term Tax: {config.costs.SHORT_TERM_TAX_RATE*100:.0f}%")
    print(f"  Long-term Tax: {config.costs.LONG_TERM_TAX_RATE*100:.1f}%")
    print()
    
    # Create strategy
    strategy = MovingAverageCrossover(fast_period=20, slow_period=50)
    
    print(f"Strategy: {strategy.name}")
    print()
    
    # Create engine and run backtest
    print("Running backtest...")
    print("-"*80)
    
    engine = PortfolioBacktestEngine(config)
    result = engine.run_strategy_single_stock(
        strategy=strategy,
        stock_data=stock_prices,
        isin=isin,
        symbol=symbol,
        exchange='NSE',
        company_name=company_name
    )
    
    # Display results
    print()
    print("="*80)
    print("RESULTS")
    print("="*80)
    print()
    
    perf = result['performance']
    
    print(f"Period: {result['period']['start'].strftime('%Y-%m-%d')} to {result['period']['end'].strftime('%Y-%m-%d')}")
    print(f"Days: {result['period']['days']}")
    print()
    
    print("PERFORMANCE:")
    print(f"  Initial Capital:  ₹{perf['initial_capital']:>12,.2f}")
    print(f"  Final Capital:    ₹{perf['final_capital']:>12,.2f}")
    print(f"  Total Return:     ₹{perf['total_return']:>12,.2f}")
    print(f"  Return %:         {perf['total_return_pct']:>12,.2f}%")
    print()
    
    print("TRADES:")
    print(f"  Total Trades:     {perf['total_trades']:>12}")
    print(f"  Winning Trades:   {perf['winning_trades']:>12}")
    print(f"  Losing Trades:    {perf['losing_trades']:>12}")
    print(f"  Win Rate:         {perf['win_rate']:>12,.2f}%")
    
    if perf['winning_trades'] > 0:
        print(f"  Average Win:      ₹{perf['avg_win']:>12,.2f}")
    if perf['losing_trades'] > 0:
        print(f"  Average Loss:     ₹{perf['avg_loss']:>12,.2f}")
    if perf['profit_factor'] > 0:
        print(f"  Profit Factor:    {perf['profit_factor']:>12,.2f}")
    print()
    
    print("COSTS & TAXES:")
    print(f"  Tax Paid:         ₹{perf['total_tax_paid']:>12,.2f}")
    print(f"  Costs Paid:       ₹{perf['total_costs_paid']:>12,.2f}")
    print(f"  Total Deducted:   ₹{perf['total_tax_paid'] + perf['total_costs_paid']:>12,.2f}")
    print()
    
    # Show sample trades
    if len(result['trades']) > 0:
        print("SAMPLE TRADES:")
        print("-"*80)
        trades_df = result['trades']
        
        # Show first 5 trades
        for idx, trade in trades_df.head(5).iterrows():
            print(f"\n{trade['date'].strftime('%Y-%m-%d')} | {trade['action']:4s} | "
                  f"Price: ₹{trade['price']:7,.2f} | Qty: {trade.get('quantity', 0):4.0f}")
            
            if trade['action'] == 'SELL':
                print(f"  → P&L: ₹{trade.get('realized_pnl', 0):+,.2f} | "
                      f"Tax: ₹{trade.get('tax_paid', 0):,.2f} | "
                      f"Holding: {trade.get('holding_days', 0)} days "
                      f"({'LT' if trade.get('is_long_term', False) else 'ST'})")
        
        if len(trades_df) > 5:
            print(f"\n... and {len(trades_df) - 5} more trades")
    
    print()
    print("="*80)
    print("✅ Test Complete!")
    print("="*80)
    
    # Save results
    print("\nSaving results...")
    result['trades'].to_csv('quick_test_trades.csv', index=False)
    result['equity_curve'].to_csv('quick_test_equity.csv', index=False)
    
    print("  ✓ Trades saved to: quick_test_trades.csv")
    print("  ✓ Equity curve saved to: quick_test_equity.csv")
    print()


if __name__ == "__main__":
    main()
