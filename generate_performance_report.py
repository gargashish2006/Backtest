
import pandas as pd
import matplotlib.pyplot as plt
# import seaborn as sns
from pathlib import Path
import numpy as np

def generate_performance_report():
    repo_root = Path(__file__).parent
    output_dir = repo_root / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    # 1. Load Data
    try:
        strat_df = pd.read_csv(output_dir / "champion_full_nav.csv")
        bench_df = pd.read_csv(output_dir / "top_1000_benchmark.csv")
    except FileNotFoundError as e:
        print(f"Error loading data: {e}")
        return

    # Clean & Align
    strat_df['date'] = pd.to_datetime(strat_df['date'])
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    
    strat_perf = strat_df[['date', 'nav']].dropna().set_index('date').sort_index()
    strat_perf.columns = ['Strategy']
    
    bench_perf = bench_df[['date', 'index_value']].dropna().set_index('date').sort_index()
    bench_perf.columns = ['Benchmark']
    
    start_date = max(strat_perf.index.min(), bench_perf.index.min())
    end_date = min(strat_perf.index.max(), bench_perf.index.max())
    
    strat_perf = strat_perf[(strat_perf.index >= start_date) & (strat_perf.index <= end_date)]
    bench_perf = bench_perf[(bench_perf.index >= start_date) & (bench_perf.index <= end_date)]
    
    combined = pd.concat([strat_perf, bench_perf], axis=1).dropna()
    
    if combined.empty:
        print("No overlapping data found!")
        return

    # Normalize to 100
    normalized = combined / combined.iloc[0] * 100
    
    # --- CHART 1: NAV Comparison ---
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')
    
    plt.plot(normalized.index, normalized['Strategy'], label='Strategy (Post-Tax/Fees)', color='#10b981', linewidth=2)
    plt.plot(normalized.index, normalized['Benchmark'], label='Top 1000 Bench (Pre-Tax/Fees)', color='#94a3b8', linewidth=1.5, alpha=0.7)
    
    plt.title('Strategy Performance vs Benchmark (2017-2026)', fontsize=16, color='white', pad=20)
    plt.ylabel('NAV (Base 100)', fontsize=12, color='gray')
    plt.legend(frameon=False)
    plt.grid(True, alpha=0.1)
    
    plt.savefig(output_dir / "full_nav_comparison.png", dpi=300, bbox_inches='tight')
    plt.close()

    # --- RETURN COMPARISONS ---
    daily_rets = combined.pct_change().dropna()
    
    # 1. Annual Returns
    yearly_rets = daily_rets.resample('YE').apply(lambda x: (1 + x).prod() - 1)
    yearly_rets.index = yearly_rets.index.year
    
    # --- CHART 2: Annual Returns ---
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')
    
    x = np.arange(len(yearly_rets))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 6))
    plt.style.use('dark_background')
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    
    rects1 = ax.bar(x - width/2, yearly_rets['Strategy'] * 100, width, label='Strategy', color='#10b981')
    rects2 = ax.bar(x + width/2, yearly_rets['Benchmark'] * 100, width, label='Benchmark', color='#64748b')
    
    ax.set_ylabel('Return (%)', color='white')
    ax.set_title('Annual Returns Comparison', color='white', fontsize=16, pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(yearly_rets.index, color='white')
    ax.tick_params(axis='y', colors='white')
    ax.legend(frameon=False, labelcolor='white')
    ax.grid(axis='y', alpha=0.1)
    
    def autolabel(rects, ax):
        for rect in rects:
            height = rect.get_height()
            offset = 3 if height >= 0 else -15
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, offset),
                        textcoords="offset points",
                        ha='center', va='bottom', color='white', fontsize=9)

    autolabel(rects1, ax)
    autolabel(rects2, ax)
    
    plt.tight_layout()
    plt.savefig(output_dir / "annual_returns_comparison.png", dpi=300)
    plt.close()
    
    # 2. Quarterly Returns
    quarterly_rets = daily_rets.resample('QE').apply(lambda x: (1 + x).prod() - 1)
    
    # --- CHART 3: Quarterly Returns Heatmap-ish Bar Chart (Selected Period: Last 12 Quarters) ---
    # Showing all 36 quarters is too crowded. Let's show the full history as a detailed grouped bar chart.
    # We might need to make it very wide or split it.
    # Let's try plotting all quarters but rotate labels heavily.
    
    plt.figure(figsize=(20, 8)) # Very wide
    plt.style.use('dark_background')
    
    # Create Quarter Labels
    q_labels = [d.strftime('%Y-Q') + str((d.month-1)//3 + 1) for d in quarterly_rets.index]
    x_q = np.arange(len(quarterly_rets))
    
    fig_q, ax_q = plt.subplots(figsize=(18, 8))
    plt.style.use('dark_background')
    ax_q.set_facecolor('#0f172a')
    fig_q.patch.set_facecolor('#0f172a')
    
    rects1q = ax_q.bar(x_q - width/2, quarterly_rets['Strategy'] * 100, width, label='Strategy', color='#10b981')
    rects2q = ax_q.bar(x_q + width/2, quarterly_rets['Benchmark'] * 100, width, label='Benchmark', color='#64748b')
    
    ax_q.set_ylabel('Return (%)', color='white')
    ax_q.set_title('Quarterly Returns Comparison (Full History)', color='white', fontsize=16, pad=20)
    ax_q.set_xticks(x_q)
    ax_q.set_xticklabels(q_labels, rotation=90, color='white', fontsize=8) # Rotate labels
    ax_q.legend(frameon=False, labelcolor='white')
    ax_q.grid(axis='y', alpha=0.1)
    
    plt.tight_layout()
    plt.savefig(output_dir / "quarterly_returns_comparison.png", dpi=300)
    print("Saved quarterly_returns_comparison.png")
    plt.close()

    # Save to CSV as well
    quarterly_out = quarterly_rets * 100
    quarterly_out = quarterly_out.round(2)
    quarterly_out.index = q_labels
    quarterly_out.to_csv(output_dir / "quarterly_returns.csv")
    
    # --- METRICS SUMMARY ---
    # Calculate Sharpe with Risk Free Rate = 6%
    rf_rate = 0.06
    rf_daily = (1 + rf_rate) ** (1/252) - 1
    
    excess_strat = daily_rets['Strategy'] - rf_daily
    excess_bench = daily_rets['Benchmark'] - rf_daily
    
    metrics = {}
    for col, excess in [('Strategy', excess_strat), ('Benchmark', excess_bench)]:
        # CAGR
        total_r = (1 + daily_rets[col]).prod() - 1
        cagr_val = (1 + total_r) ** (252 / len(daily_rets)) - 1
        
        # Volatility
        vol_val = daily_rets[col].std() * (252 ** 0.5)
        
        # Sharpe
        sharpe_val = (excess.mean() / excess.std()) * (252**0.5)
        
        # Max DD
        nav_n = normalized[col]
        dd = (nav_n / nav_n.cummax() - 1).min()
        
        metrics[col] = {
            'CAGR': cagr_val,
            'Sharpe': sharpe_val,
            'MaxDD': dd,
            'Total': total_r
        }
    
    print("\nPerformance Summary (Full Period):")
    print("-" * 50)
    print(f"{'Metric':<15} | {'Strategy':>12} | {'Benchmark':>12}")
    print("-" * 50)
    print(f"{'Total Return':<15} | {metrics['Strategy']['Total']*100:>11.1f}% | {metrics['Benchmark']['Total']*100:>11.1f}%")
    print(f"{'CAGR':<15} | {metrics['Strategy']['CAGR']*100:>11.1f}% | {metrics['Benchmark']['CAGR']*100:>11.1f}%")
    print(f"{'Sharpe (Rf=6%)':<15} | {metrics['Strategy']['Sharpe']:>12.2f} | {metrics['Benchmark']['Sharpe']:>12.2f}")
    print(f"{'Max Drawdown':<15} | {metrics['Strategy']['MaxDD']*100:>11.1f}% | {metrics['Benchmark']['MaxDD']*100:>11.1f}%")
    print("-" * 50)

if __name__ == "__main__":
    generate_performance_report()
