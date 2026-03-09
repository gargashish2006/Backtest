import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler

def run_breadth_comparison():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Dates (Every 3 months from 2018 to 2026)
    dates = []
    for y in range(2018, 2027):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            # Find closest available trade date
            avail = [d for d in dh.get_all_dates() if d >= dt]
            if avail:
                dates.append(avail[0])
    
    # Filter to unique and sorted
    dates = sorted(list(set(dates)))
    
    results = []
    
    print("Calculating aggregate industry breadth...")
    for date in dates:
        row = {'date': date}
        
        # 4Q Breadth
        sh_4q = dh.get_shareholder_trend(date, lookback_quarters=4)
        if not sh_4q.empty:
            sh_4q['industry'] = sh_4q['isin'].map(dh.isin_to_industry)
            ind_breadth_4q = sh_4q.groupby('industry')['decreased'].mean()
            row['breadth_4q'] = ind_breadth_4q.mean()
        else:
            row['breadth_4q'] = None

        # 8Q Breadth
        sh_8q = dh.get_shareholder_trend(date, lookback_quarters=8)
        if not sh_8q.empty:
            sh_8q['industry'] = sh_8q['isin'].map(dh.isin_to_industry)
            ind_breadth_8q = sh_8q.groupby('industry')['decreased'].mean()
            row['breadth_8q'] = ind_breadth_8q.mean()
        else:
            row['breadth_8q'] = None

        # 12Q Breadth
        sh_12q = dh.get_shareholder_trend(date, lookback_quarters=12)
        if not sh_12q.empty:
            sh_12q['industry'] = sh_12q['isin'].map(dh.isin_to_industry)
            ind_breadth_12q = sh_12q.groupby('industry')['decreased'].mean()
            row['breadth_12q'] = ind_breadth_12q.mean()
        else:
            row['breadth_12q'] = None
            
        # Benchmark NAV
        bench_df = dh.top_1000_bench
        if bench_df is not None:
            mask = bench_df['date'] <= date
            if mask.any():
                row['bench_nav'] = bench_df.loc[mask, 'index_value'].iloc[-1]
            else:
                row['bench_nav'] = None
        
        results.append(row)
        
    df = pd.DataFrame(results).dropna().set_index('date')
    
    # 2. Plotting
    fig, ax1 = plt.subplots(figsize=(12, 7))
    
    color_4q = 'tab:green'
    color_8q = 'tab:blue'
    color_12q = 'tab:cyan'
    
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Agg. Industry Breadth (%)', color='black')
    line0 = ax1.plot(df.index, df['breadth_4q'] * 100, label='4Q (1Y) Industry Breadth', color=color_4q, linewidth=1.5, alpha=0.7)
    line1 = ax1.plot(df.index, df['breadth_8q'] * 100, label='8Q (2Y) Industry Breadth', color=color_8q, linewidth=2)
    line2 = ax1.plot(df.index, df['breadth_12q'] * 100, label='12Q (3Y) Industry Breadth', color=color_12q, linewidth=2, linestyle='--')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.set_ylim(0, 100)
    ax1.grid(True, alpha=0.3)
    
    ax2 = ax1.twinx()
    color_bench = 'tab:red'
    ax2.set_ylabel('Top 1000 Benchmark NAV', color=color_bench)
    # Normalize bench for visual comparison or just plot it
    # Let's normalize to first date in df
    bench_scaled = (df['bench_nav'] / df['bench_nav'].iloc[0]) * 100
    line3 = ax2.plot(df.index, bench_scaled, label='Top 1000 Bench (Rebased)', color=color_bench, linewidth=2, alpha=0.6)
    ax2.tick_params(axis='y', labelcolor=color_bench)
    
    plt.title('Aggregate Industry Shareholder Breadth vs Benchmark Performance\n8Q vs 12Q Lookbacks')
    
    # Legend
    lines = line0 + line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    plt.tight_layout()
    plot_path = repo_root / "breadth_8q_12q_benchmark.png"
    plt.savefig(plot_path)
    print(f"Plot saved to: {plot_path}")

if __name__ == "__main__":
    run_breadth_comparison()
