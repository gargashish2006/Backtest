import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def compare():
    root = Path(__file__).parent
    base_path = root / "outputs/champion_full_nav.csv"
    var_path = root / "outputs/champion_2yr_nav.csv"
    
    if not base_path.exists() or not var_path.exists():
        print(f"Missing NAV files: {base_path} or {var_path}")
        return
        
    base_nav = pd.read_csv(base_path)
    var_nav = pd.read_csv(var_path)
    
    base_nav['date'] = pd.to_datetime(base_nav['date'])
    var_nav['date'] = pd.to_datetime(var_nav['date'])
    
    # Normalize to 1.0 at start
    base_nav['nav_norm'] = base_nav['nav'] / base_nav['nav'].iloc[0]
    var_nav['nav_norm'] = var_nav['nav'] / var_nav['nav'].iloc[0]
    
    plt.style.use('dark_background')
    plt.figure(figsize=(14, 7))
    plt.plot(base_nav['date'], base_nav['nav_norm'], label='Baseline (All Stocks)', color='#10b981', linewidth=2)
    plt.plot(var_nav['date'], var_nav['nav_norm'], label='Variation (Min 2yr History)', color='#f59e0b', linewidth=2)
    
    plt.title("Performance Comparison: Impact of 2-Year Price History Filter", fontsize=16, pad=20)
    plt.ylabel("Normalized NAV", fontsize=12)
    plt.xlabel("Date", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.legend(fontsize=12)
    
    out_img = root / "outputs/history_filter_comparison.png"
    plt.savefig(out_img, bbox_inches='tight')
    print(f"Comparison chart saved to {out_img}")

if __name__ == "__main__":
    compare()
