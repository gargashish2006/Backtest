
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from utils.analytics import calculate_metrics

def compare_ml_vs_champion():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    ml_path = repo_root / "outputs/ml_strategy_nav.csv"
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    
    if not ml_path.exists():
        print("ML Strategy NAV not found.")
        return
    if not champ_path.exists():
        print("Champion Strategy NAV not found.")
        return
        
    ml_df = pd.read_csv(ml_path)
    champ_df = pd.read_csv(champ_path)
    
    ml_df['date'] = pd.to_datetime(ml_df['date'])
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    
    # Filter Champion to match ML Period (Feb 2023 - Feb 2026)
    start_date = ml_df['date'].min()
    end_date = ml_df['date'].max()
    
    champ_subset = champ_df[(champ_df['date'] >= start_date) & (champ_df['date'] <= end_date)].copy()
    
    if champ_subset.empty:
        print("Champion data does not cover the ML period.")
        return
        
    # Load V2 NAV
    ml_v2_path = repo_root / "outputs/ml_strategy_v2_nav.csv"
    
    # Calculate Metrics for V1 (ml_df)
    ml_df['normalized'] = ml_df['nav'] / ml_df['nav'].iloc[0] * 100
    ml_stats = calculate_metrics(ml_df)
    
    # Calculate Metrics for Champion (champ_subset)
    champ_subset['normalized'] = champ_subset['nav'] / champ_subset['nav'].iloc[0] * 100
    c_period_df = champ_subset[['date', 'nav']].reset_index(drop=True)
    champ_stats = calculate_metrics(c_period_df)
    
    if ml_v2_path.exists():
        ml_v2_df = pd.read_csv(ml_v2_path)
        ml_v2_df['date'] = pd.to_datetime(ml_v2_df['date'])
        ml_v2_df['normalized'] = ml_v2_df['nav'] / ml_v2_df['nav'].iloc[0] * 100
        ml_v2_stats = calculate_metrics(ml_v2_df)
    else:
        ml_v2_df = None


    # Load Static V2 NAV
    static_v2_path = repo_root / "outputs/static_v2_nav.csv"
    if static_v2_path.exists():
        static_v2_df = pd.read_csv(static_v2_path)
        static_v2_df['date'] = pd.to_datetime(static_v2_df['date'])
        static_v2_df['normalized'] = static_v2_df['nav'] / static_v2_df['nav'].iloc[0] * 100
        static_v2_stats = calculate_metrics(static_v2_df)
    else:
        static_v2_df = None

    print("\n" + "="*140)
    print(f"STRATEGY COMPARISON (Out-of-Sample: {start_date.date()} to {end_date.date()})")
    print("="*140)
    print(f"{'Metric':<20} | {'ML V1':>15} | {'ML V2 (Ind)':>15} | {'Static V2':>15} | {'Champion':>15}")
    print("-" * 100)
    print(f"{'CAGR':<20} | {ml_stats['CAGR']:>15} | {ml_v2_stats['CAGR'] if ml_v2_df is not None else 'N/A':>15} | {static_v2_stats['CAGR'] if static_v2_df is not None else 'N/A':>15} | {champ_stats['CAGR']:>15}")
    print(f"{'Max Drawdown':<20} | {ml_stats['Max Drawdown']:>15} | {ml_v2_stats['Max Drawdown'] if ml_v2_df is not None else 'N/A':>15} | {static_v2_stats['Max Drawdown'] if static_v2_df is not None else 'N/A':>15} | {champ_stats['Max Drawdown']:>15}")
    print(f"{'Sharpe Ratio':<20} | {ml_stats['Sharpe Ratio']:>15} | {ml_v2_stats['Sharpe Ratio'] if ml_v2_df is not None else 'N/A':>15} | {static_v2_stats['Sharpe Ratio'] if static_v2_df is not None else 'N/A':>15} | {champ_stats['Sharpe Ratio']:>15}")
    print("="*140)
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(ml_df['date'], ml_df['normalized'], label=f'ML V1 (CAGR {ml_stats["CAGR"]})', linewidth=1, alpha=0.6)
    if ml_v2_df is not None:
        plt.plot(ml_v2_df['date'], ml_v2_df['normalized'], label=f'ML V2 (CAGR {ml_v2_stats["CAGR"]})', linewidth=1, alpha=0.6)
    if static_v2_df is not None:
        plt.plot(static_v2_df['date'], static_v2_df['normalized'], label=f'Static V2 (CAGR {static_v2_stats["CAGR"]})', linewidth=2, color='green')
    plt.plot(champ_subset['date'], champ_subset['normalized'], label=f'Champion (CAGR {champ_stats["CAGR"]})', color='black', linestyle='--')
    
    plt.title(f'ML vs Static Rules vs Champion (Out-of-Sample: 2023-2026)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    out_img = repo_root / "outputs/static_v2_comparison.png"
    plt.savefig(out_img)
    print(f"Comparison chart saved to: {out_img}")

if __name__ == "__main__":
    compare_ml_vs_champion()
