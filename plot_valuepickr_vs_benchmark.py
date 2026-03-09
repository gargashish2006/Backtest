import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# Paths
REPO = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
DB_PATH = REPO / "database" / "valuepickr_posts.parquet"
BENCHMARK_PATH = REPO / "benchmarks" / "benchmark_top1000_equal_weight_2016-02-01_to_2026-01-28.parquet"
OUTPUT_PATH = REPO / "valuepickr_vs_benchmark.png"

def main():
    print("Loading data...")
    # Load ValuePickr posts
    df_posts = pd.read_parquet(DB_PATH)
    df_posts['created_at'] = pd.to_datetime(df_posts['created_at'])
    
    # Load Benchmark
    df_benchmark = pd.read_parquet(BENCHMARK_PATH)
    df_benchmark['date'] = pd.to_datetime(df_benchmark['date'])
    df_benchmark = df_benchmark.sort_values('date')
    
    # Aggregate posts monthly
    df_posts['month'] = df_posts['created_at'].dt.tz_localize(None).dt.to_period('M').dt.to_timestamp()
    monthly_counts = df_posts.groupby('month').size().rename('post_count')
    
    # Rolling 3-month average for smoothing
    monthly_counts_smooth = monthly_counts.rolling(window=3).mean()
    
    # Align dates
    start_date = max(monthly_counts.index.min(), df_benchmark['date'].min())
    end_date = min(monthly_counts.index.max(), df_benchmark['date'].max())
    
    monthly_counts = monthly_counts[start_date:end_date]
    monthly_counts_smooth = monthly_counts_smooth[start_date:end_date]
    df_benchmark = df_benchmark[(df_benchmark['date'] >= start_date) & (df_benchmark['date'] <= end_date)]
    
    # Normalize Benchmark NAV to 100 at start
    initial_nav = df_benchmark.iloc[0]['index_value']
    df_benchmark['NAV_norm'] = (df_benchmark['index_value'] / initial_nav) * 100
    
    # Plotting
    print(f"Plotting from {start_date.date()} to {end_date.date()}...")
    fig, ax1 = plt.subplots(figsize=(14, 8))

    # LHS: Benchmark NAV
    color_nav = 'tab:blue'
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Top 1000 Index NAV (Base 100)', color=color_nav, fontsize=12)
    ax1.plot(df_benchmark['date'], df_benchmark['NAV_norm'], color=color_nav, label='Top 1000 Equal Weight', linewidth=2)
    ax1.tick_params(axis='y', labelcolor=color_nav)
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)

    # RHS: Post Counts
    ax2 = ax1.twinx()
    color_posts = 'tab:red'
    ax2.set_ylabel('Monthly ValuePickr Posts', color=color_posts, fontsize=12)
    ax2.bar(monthly_counts.index, monthly_counts, color=color_posts, alpha=0.3, width=20, label='Monthly Posts')
    ax2.plot(monthly_counts_smooth.index, monthly_counts_smooth, color=color_posts, label='3M Rolling Avg', linewidth=2)
    ax2.tick_params(axis='y', labelcolor=color_posts)

    # Intersections / Highlights
    plt.title('ValuePickr Forum Activity vs. Top 1000 Index Performance', fontsize=16, fontweight='bold')
    
    # Formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    
    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, dpi=150)
    print(f"Plot saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
