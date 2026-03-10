"""
Portfolio-Based Backtest Runner
Complete script to run strategies with portfolio management.
"""

import sys
import pandas as pd
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.backtesting.config import BacktestConfig, CONSERVATIVE_CONFIG, MODERATE_CONFIG, AGGRESSIVE_CONFIG
from src.backtesting.portfolio_engine import PortfolioBacktestEngine, run_backtest_comparison
from src.strategies.technical.moving_average_crossover import MovingAverageCrossover
from src.strategies.technical.rsi_mean_reversion import RSIMeanReversion
from src.strategies.fundamental.promoter_accumulation import PromoterAccumulation
from src.strategies.hybrid.quality_momentum import QualityMomentum
from src.strategies.technical.buy_and_hold import BuyAndHold


def load_stock_data(isin: str, database_path: str = "database") -> dict:
    """
    Load stock data from database files.
    
    Args:
        isin: Stock ISIN to load
        database_path: Path to database folder
        
    Returns:
        Dictionary with stock info and price data
    """
    db_path = Path(database_path)
    
    # Load master identifiers
    master_df = pd.read_csv(db_path / "master_identifiers.csv")
    stock_info = master_df[master_df['isin'] == isin]
    
    if len(stock_info) == 0:
        return None
    
    stock_info = stock_info.iloc[0]
    
    # Load price data
    price_df = pd.read_csv(db_path / "price_data.csv")
    stock_prices = price_df[price_df['isin'] == isin].copy()
    
    if len(stock_prices) == 0:
        return None
    
    # Convert date column
    stock_prices['date'] = pd.to_datetime(stock_prices['date'])
    stock_prices = stock_prices.sort_values('date').reset_index(drop=True)
    
    return {
        'data': stock_prices,
        'isin': isin,
        'symbol': stock_info['primary_symbol'],
        'exchange': stock_info['primary_exchange'],
        'company_name': stock_info['company_name']
    }


def load_multiple_stocks(isins: list, database_path: str = "database") -> dict:
    """
    Load data for multiple stocks.
    
    Args:
        isins: List of ISINs to load
        database_path: Path to database folder
        
    Returns:
        Dictionary mapping ISIN to stock data
    """
    stocks_data = {}
    loaded_count = 0
    
    print(f"Loading data for {len(isins)} stocks...")
    
    for idx, isin in enumerate(isins):
        stock_data = load_stock_data(isin, database_path)
        if stock_data is not None:
            stocks_data[isin] = stock_data
            loaded_count += 1
        
        if (idx + 1) % 10 == 0:
            print(f"  Loaded {loaded_count}/{idx + 1} stocks...")
    
    print(f"Successfully loaded {loaded_count}/{len(isins)} stocks\n")
    return stocks_data


def get_stock_universe(universe_type: str = "top100", database_path: str = "database") -> list:
    """
    Get list of ISINs based on universe type.
    
    Args:
        universe_type: Type of universe ('top100', 'all', 'recommended', or path to CSV)
        database_path: Path to database folder
        
    Returns:
        List of ISINs
    """
    db_path = Path(database_path)
    
    if universe_type == "all":
        # Load all stocks from master identifiers
        master_df = pd.read_csv(db_path / "master_identifiers.csv")
        return master_df['isin'].tolist()
    
    elif universe_type == "recommended":
        # Load recommended stocks for backtesting
        if (Path(project_root) / "stocks_recommended_for_backtesting.csv").exists():
            rec_df = pd.read_csv(project_root / "stocks_recommended_for_backtesting.csv")
            return rec_df['isin'].tolist()
        else:
            print("Warning: stocks_recommended_for_backtesting.csv not found. Using top 100.")
            universe_type = "top100"
    
    elif universe_type == "top100":
        # Load stocks with most data (top 100 by number of price records)
        price_df = pd.read_csv(db_path / "price_data.csv")
        top_stocks = price_df.groupby('isin').size().sort_values(ascending=False).head(100)
        return top_stocks.index.tolist()
    
    elif Path(universe_type).exists():
        # Custom CSV file
        custom_df = pd.read_csv(universe_type)
        if 'isin' in custom_df.columns:
            return custom_df['isin'].tolist()
        else:
            print(f"Error: CSV file must have 'isin' column")
            sys.exit(1)
    
    else:
        print(f"Error: Unknown universe type: {universe_type}")
        sys.exit(1)


def run_single_stock_backtest(args):
    """Run backtest on a single stock."""
    print(f"\n{'='*80}")
    print(f"Single Stock Backtest")
    print(f"{'='*80}\n")
    
    # Load stock data
    print(f"Loading data for ISIN: {args.isin}")
    stock_data = load_stock_data(args.isin, args.database)
    
    if stock_data is None:
        print(f"Error: No data found for ISIN {args.isin}")
        return
    
    print(f"Stock: {stock_data['company_name']}")
    print(f"Symbol: {stock_data['symbol']}")
    print(f"Exchange: {stock_data['exchange']}")
    print(f"Data points: {len(stock_data['data'])}")
    print()
    
    # Create configuration
    config = BacktestConfig(
        INITIAL_CAPITAL=args.capital,
        MAX_POSITIONS=args.max_positions
    )
    
    # Select strategy
    strategy = get_strategy(args.strategy)
    
    # Create engine and run
    engine = PortfolioBacktestEngine(config)
    result = engine.run_strategy_single_stock(
        strategy=strategy,
        stock_data=stock_data['data'],
        isin=stock_data['isin'],
        symbol=stock_data['symbol'],
        exchange=stock_data['exchange'],
        company_name=stock_data['company_name']
    )
    
    # Display results
    print_results(result)
    
    # Save results
    save_results(result, args.output)


def run_multi_stock_backtest(args):
    """Run backtest on multiple stocks."""
    print(f"\n{'='*80}")
    print(f"Multi-Stock Portfolio Backtest")
    print(f"{'='*80}\n")
    
    # Get stock universe
    print(f"Universe: {args.universe}")
    isins = get_stock_universe(args.universe, args.database)
    
    # Limit if specified
    if args.limit and args.limit < len(isins):
        print(f"Limiting to first {args.limit} stocks")
        isins = isins[:args.limit]
    
    # Load stock data
    stocks_data = load_multiple_stocks(isins, args.database)
    
    if len(stocks_data) == 0:
        print("Error: No valid stock data loaded")
        return
    
    # Create configuration
    config = BacktestConfig(
        INITIAL_CAPITAL=args.capital,
        MAX_POSITIONS=args.max_positions
    )
    
    # Select strategy
    strategy = get_strategy(args.strategy)
    
    # Create engine and run
    engine = PortfolioBacktestEngine(config)
    result = engine.run_strategy_multi_stock(
        strategy=strategy,
        stocks_data=stocks_data
    )
    
    # Display results
    print_results(result)
    
    # Save results
    save_results(result, args.output)


def run_comparison(args):
    """Run comparison across strategies and configurations."""
    print(f"\n{'='*80}")
    print(f"Strategy & Configuration Comparison")
    print(f"{'='*80}\n")
    
    # Get stock universe
    print(f"Universe: {args.universe}")
    isins = get_stock_universe(args.universe, args.database)
    
    if args.limit and args.limit < len(isins):
        print(f"Limiting to first {args.limit} stocks")
        isins = isins[:args.limit]
    
    # Load stock data
    stocks_data = load_multiple_stocks(isins, args.database)
    
    # Get strategies
    strategies = [
        MovingAverageCrossover(20, 50),
        RSIMeanReversion(14, 30, 70),
        PromoterAccumulation(),
        QualityMomentum()
    ]
    
    # Get configurations
    configs = [CONSERVATIVE_CONFIG, MODERATE_CONFIG, AGGRESSIVE_CONFIG]
    
    # Run comparison
    results_df = run_backtest_comparison(strategies, stocks_data, configs)
    
    # Display results
    print(f"\n{'='*80}")
    print(f"COMPARISON RESULTS")
    print(f"{'='*80}\n")
    print(results_df.to_string(index=False))
    
    # Save results
    if args.output:
        output_file = f"{args.output}_comparison.csv"
        results_df.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")


def get_strategy(strategy_name: str):
    """Get strategy object by name."""
    strategies = {
        'ma_cross': MovingAverageCrossover(20, 50),
        'ma_cross_20_50': MovingAverageCrossover(20, 50),
        'ma_cross_50_200': MovingAverageCrossover(50, 200),
        'rsi': RSIMeanReversion(14, 30, 70),
        'promoter': PromoterAccumulation(),
        'quality': QualityMomentum(),
        'buy_and_hold': BuyAndHold()
    }
    
    if strategy_name not in strategies:
        print(f"Error: Unknown strategy '{strategy_name}'")
        print(f"Available strategies: {', '.join(strategies.keys())}")
        sys.exit(1)
    
    return strategies[strategy_name]


def print_results(result: dict):
    """Print backtest results in formatted way."""
    print(f"\n{'='*80}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*80}\n")
    
    perf = result['performance']
    
    print(f"Strategy: {result['strategy']}")
    if 'stock' in result:
        print(f"Stock: {result['stock']}")
    if 'universe_size' in result:
        print(f"Universe Size: {result['universe_size']}")
        print(f"Valid Stocks: {result['valid_stocks']}")
    
    print(f"\nPeriod:")
    if 'period' in result:
        print(f"  Start: {result['period']['start']}")
        print(f"  End: {result['period']['end']}")
        print(f"  Days: {result['period']['days']}")
    
    print(f"\nPerformance:")
    print(f"  Initial Capital: ₹{perf['initial_capital']:,.2f}")
    print(f"  Final Capital: ₹{perf['final_capital']:,.2f}")
    print(f"  Total Return: {perf['total_return_pct']:,.2f}%")
    print(f"  Total P&L: ₹{perf['total_return']:,.2f}")
    
    print(f"\nTrades:")
    print(f"  Total Trades: {perf['total_trades']}")
    print(f"  Winning Trades: {perf['winning_trades']}")
    print(f"  Losing Trades: {perf['losing_trades']}")
    print(f"  Win Rate: {perf['win_rate']:.2f}%")
    
    if perf['winning_trades'] > 0:
        print(f"  Average Win: ₹{perf['avg_win']:,.2f}")
    if perf['losing_trades'] > 0:
        print(f"  Average Loss: ₹{perf['avg_loss']:,.2f}")
    if perf['profit_factor'] > 0:
        print(f"  Profit Factor: {perf['profit_factor']:.2f}")
    
    print(f"\nCosts & Taxes:")
    print(f"  Total Tax Paid: ₹{perf['total_tax_paid']:,.2f}")
    print(f"  Total Costs Paid: ₹{perf['total_costs_paid']:,.2f}")
    print(f"  Combined: ₹{perf['total_tax_paid'] + perf['total_costs_paid']:,.2f}")
    
    print(f"\nCurrent State:")
    print(f"  Open Positions: {perf['open_positions']}")
    print(f"  Cash: ₹{perf['cash']:,.2f}")
    print(f"  Invested Value: ₹{perf['invested_value']:,.2f}")


def save_results(result: dict, output_prefix: str):
    """Save results to CSV files."""
    if not output_prefix:
        return
    
    # Save trades
    trades_file = f"{output_prefix}_trades.csv"
    result['trades'].to_csv(trades_file, index=False)
    print(f"\nTrades saved to: {trades_file}")
    
    # Save equity curve
    equity_file = f"{output_prefix}_equity.csv"
    result['equity_curve'].to_csv(equity_file, index=False)
    print(f"Equity curve saved to: {equity_file}")
    
    # Save performance summary
    perf_file = f"{output_prefix}_performance.csv"
    perf_df = pd.DataFrame([result['performance']])
    perf_df.to_csv(perf_file, index=False)
    print(f"Performance saved to: {perf_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio-Based Backtesting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single stock backtest
  python run_portfolio_backtest.py single --isin INE002A01018 --strategy ma_cross
  
  # Multi-stock backtest with top 100 stocks
  python run_portfolio_backtest.py multi --universe top100 --strategy ma_cross --max-positions 20
  
  # Compare all strategies with different position limits
  python run_portfolio_backtest.py compare --universe recommended --limit 50
  
  # Custom stock list
  python run_portfolio_backtest.py multi --universe my_stocks.csv --strategy rsi --capital 500000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Single stock backtest
    single_parser = subparsers.add_parser('single', help='Run backtest on single stock')
    single_parser.add_argument('--isin', required=True, help='Stock ISIN')
    single_parser.add_argument('--strategy', default='ma_cross', help='Strategy to use')
    single_parser.add_argument('--capital', type=float, default=100000, help='Initial capital')
    single_parser.add_argument('--max-positions', type=int, default=1, help='Max positions (use 1 for single stock)')
    single_parser.add_argument('--database', default='database', help='Database folder path')
    single_parser.add_argument('--output', help='Output file prefix')
    
    # Multi-stock backtest
    multi_parser = subparsers.add_parser('multi', help='Run backtest on multiple stocks')
    multi_parser.add_argument('--universe', default='top100', help='Stock universe: top100, all, recommended, or CSV path')
    multi_parser.add_argument('--strategy', default='ma_cross', help='Strategy to use')
    multi_parser.add_argument('--capital', type=float, default=100000, help='Initial capital')
    multi_parser.add_argument('--max-positions', type=int, default=10, help='Max concurrent positions')
    multi_parser.add_argument('--limit', type=int, help='Limit number of stocks')
    multi_parser.add_argument('--database', default='database', help='Database folder path')
    multi_parser.add_argument('--output', help='Output file prefix')
    
    # Comparison
    compare_parser = subparsers.add_parser('compare', help='Compare strategies and configurations')
    compare_parser.add_argument('--universe', default='top100', help='Stock universe')
    compare_parser.add_argument('--limit', type=int, default=50, help='Limit number of stocks')
    compare_parser.add_argument('--database', default='database', help='Database folder path')
    compare_parser.add_argument('--output', default='comparison', help='Output file prefix')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run appropriate command
    if args.command == 'single':
        run_single_stock_backtest(args)
    elif args.command == 'multi':
        run_multi_stock_backtest(args)
    elif args.command == 'compare':
        run_comparison(args)


if __name__ == "__main__":
    main()
