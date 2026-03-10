"""
Test Portfolio Backtest on Top 10 Stocks
Run backtest on multiple quality stocks to validate the system.
"""

import sys
import pandas as pd
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backtesting.config import BacktestConfig, CONSERVATIVE_CONFIG, MODERATE_CONFIG
from src.backtesting.portfolio_engine import PortfolioBacktestEngine
from src.strategies.technical.moving_average_crossover import MovingAverageCrossover


def main():
    print("="*80)
    print("PORTFOLIO BACKTEST - TOP 10 STOCKS TEST")
    print("="*80)
    print()
    
    # Load data
    db_path = Path("database")
    master_df = pd.read_csv(db_path / "master_identifiers.csv")
    price_df = pd.read_csv(db_path / "price_data.csv")
    
    # Get stocks with most data points (more data = better backtests)
    stock_counts = price_df.groupby('isin').size().sort_values(ascending=False)
    top_10_isins = stock_counts.head(10).index.tolist()
    
    print("Loading top 10 stocks by data availability...")
    
    # Load stock data
    stocks_data = {}
    for isin in top_10_isins:
        stock_info = master_df[master_df['isin'] == isin].iloc[0]
        stock_prices = price_df[price_df['isin'] == isin].copy()
        stock_prices['date'] = pd.to_datetime(stock_prices['date'])
        stock_prices = stock_prices.sort_values('date').reset_index(drop=True)
        
        stocks_data[isin] = {
            'data': stock_prices,
            'isin': isin,
            'symbol': stock_info['primary_symbol'],
            'exchange': stock_info['primary_exchange'],
            'company_name': stock_info['company_name']
        }
        
        print(f"  ✓ {stock_info['company_name']} ({stock_info['primary_symbol']}) - "
              f"{len(stock_prices)} days")
    
    print()
    
    # Configuration - 10 max positions for 10 stocks
    config = CONSERVATIVE_CONFIG  # 10 max positions, ₹1 Lakh capital
    
    print("Configuration:")
    print(f"  Initial Capital: ₹{config.INITIAL_CAPITAL:,.0f}")
    print(f"  Max Positions: {config.MAX_POSITIONS}")
    print(f"  Capital per Position: ₹{config.capital_per_position():,.0f}")
    print()
    
    # Strategy
    strategy = MovingAverageCrossover(20, 50)
    print(f"Strategy: {strategy.name}")
    print()
    
    # Run backtest
    print("="*80)
    print("STARTING BACKTEST")
    print("="*80)
    
    engine = PortfolioBacktestEngine(config)
    result = engine.run_strategy_multi_stock(
        strategy=strategy,
        stocks_data=stocks_data
    )
    
    # Detailed results
    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    
    perf = result['performance']
    
    print(f"\nStrategy: {result['strategy']}")
    print(f"Universe: {result['universe_size']} stocks")
    print(f"Period: {result['period']['start'].strftime('%Y-%m-%d')} to "
          f"{result['period']['end'].strftime('%Y-%m-%d')} ({result['period']['days']} days)")
    
    print("\n" + "-"*80)
    print("PORTFOLIO PERFORMANCE")
    print("-"*80)
    print(f"Initial Capital:        ₹{perf['initial_capital']:>15,.2f}")
    print(f"Final Capital:          ₹{perf['final_capital']:>15,.2f}")
    print(f"Total Return:           ₹{perf['total_return']:>15,.2f}")
    print(f"Return %:               {perf['total_return_pct']:>15,.2f}%")
    print(f"Realized P&L:           ₹{perf['total_realized_pnl']:>15,.2f}")
    print(f"Unrealized P&L:         ₹{perf['total_unrealized_pnl']:>15,.2f}")
    
    print("\n" + "-"*80)
    print("TRADE STATISTICS")
    print("-"*80)
    print(f"Total Trades:           {perf['total_trades']:>15}")
    print(f"Winning Trades:         {perf['winning_trades']:>15}")
    print(f"Losing Trades:          {perf['losing_trades']:>15}")
    print(f"Win Rate:               {perf['win_rate']:>15,.2f}%")
    
    if perf['winning_trades'] > 0:
        print(f"Average Win:            ₹{perf['avg_win']:>15,.2f}")
        print(f"Largest Win:            ₹{perf['largest_win']:>15,.2f}")
    
    if perf['losing_trades'] > 0:
        print(f"Average Loss:           ₹{perf['avg_loss']:>15,.2f}")
        print(f"Largest Loss:           ₹{perf['largest_loss']:>15,.2f}")
    
    if perf['profit_factor'] > 0:
        print(f"Profit Factor:          {perf['profit_factor']:>15,.2f}x")
    
    print("\n" + "-"*80)
    print("COSTS & TAXES BREAKDOWN")
    print("-"*80)
    print(f"Total Tax Paid:         ₹{perf['total_tax_paid']:>15,.2f}")
    print(f"Total Costs Paid:       ₹{perf['total_costs_paid']:>15,.2f}")
    print(f"Combined Deductions:    ₹{perf['total_tax_paid'] + perf['total_costs_paid']:>15,.2f}")
    print(f"As % of Gross P&L:      {(perf['total_tax_paid'] + perf['total_costs_paid']) / abs(perf['total_realized_pnl']) * 100 if perf['total_realized_pnl'] != 0 else 0:>15,.2f}%")
    
    print("\n" + "-"*80)
    print("CURRENT PORTFOLIO STATE")
    print("-"*80)
    print(f"Open Positions:         {perf['open_positions']:>15}")
    print(f"Cash Balance:           ₹{perf['cash']:>15,.2f}")
    print(f"Invested Value:         ₹{perf['invested_value']:>15,.2f}")
    print(f"Market Value:           ₹{perf['market_value']:>15,.2f}")
    
    # Trade breakdown by stock
    if len(result['trades']) > 0:
        trades_df = result['trades']
        sell_trades = trades_df[trades_df['action'] == 'SELL']
        
        if len(sell_trades) > 0:
            print("\n" + "-"*80)
            print("TRADES BY STOCK")
            print("-"*80)
            
            stock_summary = sell_trades.groupby('symbol').agg({
                'realized_pnl': ['count', 'sum', 'mean'],
                'tax_paid': 'sum',
                'holding_days': 'mean'
            }).round(2)
            
            stock_summary.columns = ['Trades', 'Total P&L', 'Avg P&L', 'Tax Paid', 'Avg Hold Days']
            print(stock_summary.to_string())
    
    # Sample trades
    if len(result['trades']) > 0:
        print("\n" + "-"*80)
        print("SAMPLE TRADES (First 10)")
        print("-"*80)
        
        for idx, trade in result['trades'].head(10).iterrows():
            date_str = trade['date'].strftime('%Y-%m-%d')
            
            if trade['action'] == 'BUY':
                print(f"{date_str} | BUY  | {trade['symbol']:10s} | "
                      f"₹{trade['price']:7,.2f} x {trade['quantity']:4.0f} = "
                      f"₹{trade['investment']:9,.2f}")
            else:
                print(f"{date_str} | SELL | {trade['symbol']:10s} | "
                      f"₹{trade['price']:7,.2f} x {trade['quantity']:4.0f} | "
                      f"P&L: ₹{trade.get('realized_pnl', 0):+9,.2f} | "
                      f"{trade.get('holding_days', 0):3.0f}d "
                      f"({'LT' if trade.get('is_long_term') else 'ST'})")
    
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    # Save files
    result['trades'].to_csv('top10_trades.csv', index=False)
    result['equity_curve'].to_csv('top10_equity.csv', index=False)
    
    # Save summary
    summary_df = pd.DataFrame([perf])
    summary_df.to_csv('top10_summary.csv', index=False)
    
    print("  ✓ Trades: top10_trades.csv")
    print("  ✓ Equity Curve: top10_equity.csv")
    print("  ✓ Summary: top10_summary.csv")
    
    print("\n" + "="*80)
    print("✅ BACKTEST COMPLETE!")
    print("="*80)
    print()


if __name__ == "__main__":
    main()
