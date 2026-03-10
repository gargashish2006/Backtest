import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_performance():
    res_dir = Path('/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/my-backtesting-engine/strategies/outputs/net_net')
    
    # Define Top 4 strategies to plot
    top_4 = [
        'Sync15_RSNP_Top1000_Large_net_net.csv',
        'IM_Top1000_Small_net_net.csv',
        'Sync15_RSNP_Top1000_Small_net_net.csv',
        'IM_Top1000_Large_net_net.csv'
    ]
    
    plt.figure(figsize=(15, 12))
    
    # Subplot 1: NAV Curves
    ax1 = plt.subplot(2, 1, 1)
    
    # Subplot 2: Drawdowns
    ax2 = plt.subplot(2, 1, 2)
    
    for filename in top_4:
        f_path = res_dir / filename
        if not f_path.exists():
            continue
            
        df = pd.read_csv(f_path)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Strategy Label
        label = filename.replace('_net_net.csv', '').replace('Sync15_RSNP_Top1000_', 'SHP-').replace('IM_Top1000_', 'IM-')
        
        # Plot NAV (Normalized to 100 for better comparison)
        nav = df['value'] / df['value'].iloc[0] * 100
        ax1.plot(df['date'], nav, label=f"{label} (CAGR: {((nav.iloc[-1]/100)**(1/((df['date'].max()-df['date'].min()).days/365.25))-1)*100:.1f}%)", linewidth=2)
        
        # Plot Drawdown
        peak = df['value'].cummax()
        dd = (df['value'] - peak) / peak * 100
        ax2.fill_between(df['date'], dd, 0, alpha=0.3, label=label)
        ax2.plot(df['date'], dd, linewidth=1)

    # Styling ax1
    ax1.set_title('Top 4 Champions: Net NAV Strategy Competition (Normalized to 100)', fontsize=16, fontweight='bold')
    ax1.set_ylabel('NAV (Log Scale Recommended)', fontsize=12)
    ax1.set_yscale('log') # Use log scale for long-term growth
    ax1.grid(True, which="both", ls="-", alpha=0.5)
    ax1.legend(loc='upper left', fontsize=10)
    
    # Styling ax2
    ax2.set_title('Underwater Drawdown Maps (Stress Test Focus)', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.set_ylim(-50, 2)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower left', fontsize=10)
    
    plt.tight_layout()
    
    # Save to artifacts directory
    output_path = '/Users/shubhrakasana/.gemini/antigravity/brain/f5a57827-91d7-44c1-8f44-e1b548e0d947/champion_nav_drawdown.png'
    plt.savefig(output_path, dpi=120)
    print(f"Plot saved to: {output_path}")

if __name__ == "__main__":
    plot_performance()
