import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def plot_sensitivity_3d():
    repo_root = Path(__file__).parent
    csv_path = repo_root / "outputs/sensitivity_3d_summary.csv"
    if not csv_path.exists():
        print("CSV not found.")
        return
        
    df = pd.read_csv(csv_path)
    df = df[df['Group'] != 'Champion']
    
    # CAGR formatting
    df['CAGR_val'] = df['CAGR'].str.rstrip('%').astype(float) / 100
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # RSNP High Heatmap
    df_high = df[df['RSNP'] == 'High'].pivot(index="Group", columns="Breadth", values="CAGR_val")
    df_high = df_high.loc[['Top', 'Bottom'], ['High', 'Low']]
    im1 = ax1.imshow(df_high.values, cmap="RdYlGn")
    ax1.set_title("RSNP >= 0.40 (High Mode)")
    
    # RSNP Low Heatmap
    df_low = df[df['RSNP'] == 'Low'].pivot(index="Group", columns="Breadth", values="CAGR_val")
    df_low = df_low.loc[['Top', 'Bottom'], ['High', 'Low']]
    im2 = ax2.imshow(df_low.values, cmap="RdYlGn")
    ax2.set_title("RSNP < 0.40 (Low Mode)")
    
    for ax, p_df in zip([ax1, ax2], [df_high, df_low]):
        ax.set_xticks(np.arange(len(p_df.columns)))
        ax.set_yticks(np.arange(len(p_df.index)))
        ax.set_xticklabels(p_df.columns)
        ax.set_yticklabels(p_df.index)
        ax.set_xlabel("Industry Breadth (>=50% vs <50%)")
        ax.set_ylabel("Group Selection (Top vs Bottom)")
        
        for i in range(len(p_df.index)):
            for j in range(len(p_df.columns)):
                ax.text(j, i, f"{p_df.iloc[i, j]:.1%}", ha="center", va="center", color="black", weight='bold', fontsize=12)

    plt.suptitle("3D Strategy Sensitivity: CAGR % (Group x Breadth x RSNP)", fontsize=16)
    plt.tight_layout()
    plt.savefig(repo_root / "outputs/sensitivity_3d_heatmap.png")
    print(f"3D Heatmap saved to: {repo_root / 'outputs/sensitivity_3d_heatmap.png'}")

if __name__ == "__main__":
    plot_sensitivity_3d()
