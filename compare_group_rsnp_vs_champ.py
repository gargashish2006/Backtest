
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from utils.analytics import calculate_metrics

def compare_group_rsnp_vs_champ():
    repo_root = Path(__file__).parent
    
    # Load NAVs
    champ_path = repo_root / "outputs/final_champion_nav.csv"
    group_path = repo_root / "outputs/group_rsnp_nav.csv"
    
    if not champ_path.exists():
        print("Champion NAV not found.")
        return
        
    if not group_path.exists():
        print("Group RSNP NAV not found.")
        return
        
    champ_df = pd.read_csv(champ_path)
    group_df = pd.read_csv(group_path)
    
    champ_df['date'] = pd.to_datetime(champ_df['date'])
    group_df['date'] = pd.to_datetime(group_df['date'])
    
    # Match dates (Group RSNP runs on Out-of-Sample)
    start_date = group_df['date'].min()
    end_date = group_df['date'].max()
    
    champ_subset = champ_df[(champ_df['date'] >= start_date) & (champ_df['date'] <= end_date)].copy()
    
    # Calculate Metrics
    champ_subset['normalized'] = champ_subset['nav'] / champ_subset['nav'].iloc[0] * 100
    c_df = champ_subset[['date', 'nav']].reset_index(drop=True)
    champ_stats = calculate_metrics(c_df)
    
    group_df['normalized'] = group_df['nav'] / group_df['nav'].iloc[0] * 100
    group_stats = calculate_metrics(group_df)
    
    print("\n" + "="*80)
    print(f"STRATEGY COMPARISON (Feb 2023 - Feb 2026)")
    print("="*80)
    print(f"{'Metric':<20} | {'Group RSNP':>15} | {'Champion (Ind RSNP)':>20}")
    print("-" * 60)
    print(f"{'CAGR':<20} | {group_stats['CAGR']:>15} | {champ_stats['CAGR']:>20}")
    print(f"{'Max Drawdown':<20} | {group_stats['Max Drawdown']:>15} | {champ_stats['Max Drawdown']:>20}")
    print(f"{'Sharpe Ratio':<20} | {group_stats['Sharpe Ratio']:>15} | {champ_stats['Sharpe Ratio']:>20}")
    print("="*80)
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(group_df['date'], group_df['normalized'], label=f"Group RSNP (CAGR {group_stats['CAGR']})", linewidth=2, color='orange')
    plt.plot(champ_subset['date'], champ_subset['normalized'], label=f"Champion (CAGR {champ_stats['CAGR']})", color='black', linestyle='--')
    
    plt.title("Industry Ranking: Group RSNP vs Industry RSNP")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    out_img = repo_root / "outputs/group_rsnp_comparison.png"
    plt.savefig(out_img)
    print(f"Chart saved to {out_img}")

if __name__ == "__main__":
    compare_group_rsnp_vs_champ()
