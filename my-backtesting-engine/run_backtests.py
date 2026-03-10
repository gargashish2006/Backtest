#!/usr/bin/env python3
"""
Multi-Strategy Backtesting Runner
Run and compare multiple strategies on selected stocks.
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.loaders import DatabaseLoader
from src.strategies.technical import MovingAverageCrossover, RSIMeanReversion
from src.strategies.fundamental import PromoterAccumulation
from src.strategies.hybrid import QualityMomentum


def run_single_stock_backtest(
    isin: str,
    strategy,
    loader: DatabaseLoader,
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000.0
) -> Dict:
    """
    Run backtest for a single stock with a strategy.
    
    Args:
        isin: Stock ISIN
        strategy: Strategy instance
        loader: DatabaseLoader instance
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_capital: Starting capital
        
    Returns:
        Dictionary with backtest results
    """
    try:
        # Get stock info
        stock_info = loader.get_stock_info(isin)
        
        # Load price data
        price_data = loader.get_price_data_for_stock(isin, start_date, end_date)
        
        if len(price_data) < 100:  # Need minimum data
            return {
                'isin': isin,
                'company_name': stock_info['company_name'],
                'status': 'INSUFFICIENT_DATA',
                'data_points': len(price_data)
            }
        
        # Check if strategy needs shareholding data
        if hasattr(strategy, 'generate_signals') and 'shareholding_data' in strategy.generate_signals.__code__.co_varnames:
            # Load shareholding data
            shareholding_data = loader.load_shareholding_patterns(isins=[isin])
            if len(shareholding_data) == 0:
                return {
                    'isin': isin,
                    'company_name': stock_info['company_name'],
                    'status': 'NO_SHAREHOLDING_DATA'
                }
            result = strategy.backtest(price_data, shareholding_data, initial_capital)
        else:
            # Technical strategy - only needs price data
            result = strategy.backtest(price_data, initial_capital)
        
        # Add stock info to results
        result['isin'] = isin
        result['company_name'] = stock_info['company_name']
        result['nse_symbol'] = stock_info.get('nse_symbol', '')
        result['bse_code'] = stock_info.get('bse_code', '')
        result['status'] = 'SUCCESS'
        
        return result
        
    except Exception as e:
        return {
            'isin': isin,
            'status': 'ERROR',
            'error': str(e)
        }


def run_multi_stock_backtest(
    isins: List[str],
    strategies: List,
    loader: DatabaseLoader,
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000.0
) -> pd.DataFrame:
    """
    Run multiple strategies on multiple stocks.
    
    Args:
        isins: List of ISINs to backtest
        strategies: List of strategy instances
        loader: DatabaseLoader instance
        start_date: Start date
        end_date: End date
        initial_capital: Starting capital
        
    Returns:
        DataFrame with consolidated results
    """
    results = []
    
    total = len(isins) * len(strategies)
    current = 0
    
    for isin in isins:
        for strategy in strategies:
            current += 1
            print(f"\r[{current}/{total}] Running {strategy.name} on {isin}...", end='')
            
            result = run_single_stock_backtest(
                isin, 
                strategy, 
                loader, 
                start_date, 
                end_date, 
                initial_capital
            )
            
            if result['status'] == 'SUCCESS':
                metrics = result['metrics']
                results.append({
                    'isin': result['isin'],
                    'company_name': result['company_name'],
                    'nse_symbol': result.get('nse_symbol', ''),
                    'strategy': result['strategy'],
                    'total_return_pct': metrics['total_return_pct'],
                    'num_trades': metrics['num_trades'],
                    'win_rate': metrics['win_rate'],
                    'avg_return_per_trade': metrics['avg_return_per_trade'],
                    'max_drawdown_pct': metrics['max_drawdown_pct'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'final_capital': metrics['final_capital']
                })
    
    print()  # New line after progress
    return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description='Run backtesting strategies')
    parser.add_argument('--stocks', type=int, default=10, help='Number of stocks to test (default: 10)')
    parser.add_argument('--min-quality', type=float, default=7.0, help='Minimum quality score (default: 7.0)')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000.0, help='Initial capital (default: 100000)')
    parser.add_argument('--output', type=str, default='results/backtest_results.csv', help='Output file')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("MULTI-STRATEGY BACKTESTING RUNNER")
    print("=" * 80)
    
    # Load database
    print("\n1. Loading database...")
    loader = DatabaseLoader('database')
    
    # Get high-quality stocks
    print(f"2. Selecting top {args.stocks} stocks (min quality: {args.min_quality})...")
    stats = loader.load_stock_statistics()
    high_quality = stats[stats['quality_score'] >= args.min_quality].sort_values('quality_score', ascending=False)
    selected_isins = high_quality.head(args.stocks)['isin'].tolist()
    print(f"   Selected {len(selected_isins)} stocks")
    
    # Define strategies to test
    print("\n3. Initializing strategies...")
    strategies = [
        MovingAverageCrossover(fast_period=20, slow_period=50, ma_type='SMA'),
        MovingAverageCrossover(fast_period=20, slow_period=50, ma_type='EMA'),
        RSIMeanReversion(rsi_period=14, oversold_level=30, overbought_level=70),
        PromoterAccumulation(min_increase_pct=1.0, holding_period=90),
        QualityMomentum(min_promoter_pct=50.0, lookback_days=60, min_momentum_pct=10.0)
    ]
    
    for strat in strategies:
        print(f"   - {strat.name}")
    
    # Run backtests
    print(f"\n4. Running backtests...")
    print(f"   Period: {args.start_date or 'ALL'} to {args.end_date or 'ALL'}")
    print(f"   Initial Capital: ₹{args.capital:,.2f}")
    
    results_df = run_multi_stock_backtest(
        selected_isins,
        strategies,
        loader,
        args.start_date,
        args.end_date,
        args.capital
    )
    
    # Save results
    print(f"\n5. Saving results to {args.output}...")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(args.output, index=False)
    
    # Display summary
    print("\n" + "=" * 80)
    print("BACKTEST SUMMARY")
    print("=" * 80)
    
    if len(results_df) > 0:
        print("\nTop 10 Results by Total Return:")
        top_results = results_df.sort_values('total_return_pct', ascending=False).head(10)
        print(top_results[['company_name', 'strategy', 'total_return_pct', 'num_trades', 'win_rate', 'sharpe_ratio']].to_string(index=False))
        
        print("\n\nStrategy Performance Summary:")
        strategy_summary = results_df.groupby('strategy').agg({
            'total_return_pct': ['mean', 'median', 'std'],
            'win_rate': 'mean',
            'sharpe_ratio': 'mean',
            'num_trades': 'mean'
        }).round(2)
        print(strategy_summary)
        
        # Save summary
        summary_file = args.output.replace('.csv', '_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("BACKTEST SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total Stocks: {len(selected_isins)}\n")
            f.write(f"Strategies Tested: {len(strategies)}\n")
            f.write(f"Total Backtests: {len(results_df)}\n")
            f.write(f"Period: {args.start_date or 'ALL'} to {args.end_date or 'ALL'}\n")
            f.write(f"Initial Capital: ₹{args.capital:,.2f}\n\n")
            f.write("Strategy Performance:\n")
            f.write(strategy_summary.to_string())
        
        print(f"\n✅ Results saved to: {args.output}")
        print(f"✅ Summary saved to: {summary_file}")
    else:
        print("\n⚠️  No successful backtests completed.")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
