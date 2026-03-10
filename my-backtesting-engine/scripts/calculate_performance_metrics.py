import pandas as pd
import numpy as np
import os
from pathlib import Path

def calculate_metrics(file_path):
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Quarterly Returns
    df['returns'] = df['value'].pct_change()
    
    # CAGRs
    years = (df['date'].max() - df['date'].min()).days / 365.25
    total_ret = (df['value'].iloc[-1] / df['value'].iloc[0]) - 1
    cagr = (1 + total_ret)**(1/years) - 1
    
    # Volatility (Annualized from Quarterly)
    # std * sqrt(4) because we have quarterly data
    vol = df['returns'].std() * np.sqrt(4)
    
    # Sharpe Ratio (6% Risk Free Rate)
    rf = 0.06
    sharpe = (cagr - rf) / vol if vol != 0 else 0
    
    # Max Drawdown
    df['peak'] = df['value'].cummax()
    df['dd'] = (df['value'] - df['peak']) / df['peak']
    mdd = df['dd'].min()
    
    return {
        'Strategy': Path(file_path).stem.replace('_net_net', ''),
        'CAGR': cagr * 100,
        'Vol': vol * 100,
        'Sharpe': sharpe,
        'MaxDD': mdd * 100
    }

def main():
    res_dir = Path('/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/my-backtesting-engine/strategies/outputs/net_net')
    files = list(res_dir.glob('*.csv'))
    
    results = []
    for f in files:
        try:
            results.append(calculate_metrics(f))
        except Exception as e:
            print(f"Error processing {f}: {e}")
            
    perf_df = pd.DataFrame(results).sort_values('CAGR', ascending=False)
    
    print("\n" + "="*80)
    print(f"{'Strategy':<35} | {'CAGR (%)':>8} | {'Sharpe':>6} | {'MaxDD (%)':>9}")
    print("-" * 80)
    for _, row in perf_df.iterrows():
        print(f"{row['Strategy']:<35} | {row['CAGR']:>8.1f}% | {row['Sharpe']:>6.2f} | {row['MaxDD']:>9.1f}%")
    print("="*80)

if __name__ == "__main__":
    main()
