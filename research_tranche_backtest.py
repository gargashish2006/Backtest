import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
from data.data_handler import DataHandler

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

def get_quarter_labels(signal_date, lookback_quarters):
    year, month = signal_date.year, signal_date.month
    quarters = ["Mar", "Jun", "Sep", "Dec"]
    if month >= 2 and month < 5:    start_code, base_year = "Dec", year - 1
    elif month >= 5 and month < 8:  start_code, base_year = "Mar", year
    elif month >= 8 and month < 11: start_code, base_year = "Jun", year
    else:                           start_code, base_year = "Sep", year
    
    linear_map = {"Mar": 0, "Jun": 1, "Sep": 2, "Dec": 3}
    linear_curr = base_year * 4 + linear_map[start_code]
    linear_prev = linear_curr - lookback_quarters
    prev_code = quarters[linear_prev % 4]
    prev_year = linear_prev // 4
    return f"{start_code}-{base_year}", f"{prev_code}-{prev_year}"

def get_price_on_date(target_date):
    available = dh.price_df[dh.price_df['date'] <= target_date]
    if available.empty: return pd.Series(dtype=float)
    latest = available['date'].max()
    return available[available['date'] == latest].set_index('isin')['close']

def run_tranche_backtest(lookback_q=12, hold_years=3):
    """
    Runs rolling tranche backtests for a specific SH lookback and hold period.
    Returns: DataFrame of results per tranche.
    """
    all_dates = sorted(dh.get_all_dates())
    # Entry dates: Quarterly rebalance dates from 2017 to late enough for the hold period
    start_year = 2017
    # 2026 is latest, so for 3Y hold, 2023 is latest start.
    end_year = 2026 - hold_years
    
    r_dates = []
    for y in range(start_year, end_year + 1):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            # Find nearest trading day >= dt
            trading_days = [d for d in all_dates if d >= dt]
            if trading_days:
                r_dates.append(trading_days[0])
    
    tranche_results = []
    
    for entry_date in r_dates:
        signal_date = entry_date - pd.Timedelta(days=7)
        actual_signal_date = max([d for d in all_dates if d <= signal_date])
        exit_date = entry_date + pd.DateOffset(years=hold_years)
        # Find nearest trading day <= exit_date
        exit_trading_days = [d for d in all_dates if d <= exit_date]
        if not exit_trading_days: continue
        actual_exit_date = max(exit_trading_days)

        # 1. Selection
        universe = dh.get_universe(actual_signal_date, size=1000)
        u_isins = set(universe['isin'].tolist())
        
        # Shareholder signal
        curr_q, prev_q = get_quarter_labels(actual_signal_date, lookback_q)
        sh_df = dh.shareholding_df
        curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'c_sh'})
        prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'p_sh'})
        
        if curr_sh.empty or prev_sh.empty: continue
        
        merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
        merged = merged[merged['isin'].isin(u_isins)]
        merged['sh_dec'] = merged['curr_sh'] < merged['prev_sh'] if 'curr_sh' in merged else merged['c_sh'] < merged['p_sh']
        merged['industry'] = merged['isin'].map(dh.isin_to_industry)
        
        ind_stats = merged.groupby('industry')['sh_dec'].mean().reset_index()
        top_industries = ind_stats.sort_values('sh_dec', ascending=False).head(5)['industry'].tolist()
        
        # Select stocks: Top 3 by M-cap per industry
        selected = []
        for ind in top_industries:
            ind_stocks = universe[universe['isin'].map(dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
            selected.extend(ind_stocks.head(3)['isin'].tolist())
            
        if not selected: continue
        
        # 2. Performance
        p0 = get_price_on_date(entry_date)
        p1 = get_price_on_date(actual_exit_date)
        
        # Strategy Return (Equal weighted)
        portfolio_rets = []
        for isin in selected:
            if isin in p0.index and isin in p1.index and p0[isin] > 0:
                portfolio_rets.append((p1[isin] / p0[isin]) - 1)
        
        if not portfolio_rets: continue
        strat_return = np.mean(portfolio_rets)
        
        # Benchmark Return (Top 1000 Equal Weight)
        bench_isins = list(u_isins)
        bench_rets = []
        for isin in bench_isins:
            if isin in p0.index and isin in p1.index and p0[isin] > 0:
                bench_rets.append((p1[isin] / p0[isin]) - 1)
        bench_return = np.mean(bench_rets) if bench_rets else 0
        
        tranche_results.append({
            'entry_date': entry_date,
            'exit_date': actual_exit_date,
            'strat_return': strat_return,
            'bench_return': bench_return,
            'excess_return': strat_return - bench_return,
            'num_stocks': len(portfolio_rets)
        })
        
    return pd.DataFrame(tranche_results)

def main():
    horizons = [1, 2, 3] # Years
    lookbacks = [4, 8, 12] # Quarters
    
    summary_results = []
    
    for h in horizons:
        for lb in lookbacks:
            print(f"Running Backtest: {lb}Q Lookback, {h}Y Hold...")
            df = run_tranche_backtest(lookback_q=lb, hold_years=h)
            if df.empty: continue
            
            batting_avg = (df['excess_return'] > 0).mean()
            mean_alpha = df['excess_return'].mean()
            mean_return = df['strat_return'].mean()
            mean_bench = df['bench_return'].mean()
            
            summary_results.append({
                'Lookback': f"SH-{lb}Q",
                'Hold_Period': f"{h}Y",
                'Num_Tranches': len(df),
                'Mean_Return': mean_return,
                'Mean_Bench': mean_bench,
                'Mean_Alpha': mean_alpha,
                'Win_Rate': batting_avg
            })
            
    df_summary = pd.DataFrame(summary_results)
    print("\nLong-Term Tranche Performance Summary:")
    print(df_summary)
    
    # Visualization: Alpha by Hold Period and Lookback
    pivot_alpha = df_summary.pivot(index='Lookback', columns='Hold_Period', values='Mean_Alpha')
    pivot_win = df_summary.pivot(index='Lookback', columns='Hold_Period', values='Win_Rate')
    
    plt.figure(figsize=(14, 6))
    
    plt.subplot(1, 2, 1)
    im1 = plt.imshow(pivot_alpha.values, cmap='RdYlGn', interpolation='nearest')
    plt.title("Mean Alpha (Excess Return) vs Benchmark")
    plt.xticks(range(len(pivot_alpha.columns)), pivot_alpha.columns)
    plt.yticks(range(len(pivot_alpha.index)), pivot_alpha.index)
    plt.colorbar(im1)
    for i in range(len(pivot_alpha.index)):
        for j in range(len(pivot_alpha.columns)):
            plt.text(j, i, f"{pivot_alpha.iloc[i, j]:.2%}", ha="center", va="center")
            
    plt.subplot(1, 2, 2)
    im2 = plt.imshow(pivot_win.values, cmap='RdYlGn', interpolation='nearest')
    plt.title("Win Rate (Batting Average) vs Benchmark")
    plt.xticks(range(len(pivot_win.columns)), pivot_win.columns)
    plt.yticks(range(len(pivot_win.index)), pivot_win.index)
    plt.colorbar(im2)
    for i in range(len(pivot_win.index)):
        for j in range(len(pivot_win.columns)):
            plt.text(j, i, f"{pivot_win.iloc[i, j]:.0%}", ha="center", va="center")
            
    plt.tight_layout()
    plt.savefig(repo_root / "tranche_performance_matrix.png")
    
    # Save raw results for review
    df_summary.to_csv(repo_root / "tranche_backtest_summary.csv", index=False)
    print(f"\nResults saved to tranche_backtest_summary.csv and tranche_performance_matrix.png")

if __name__ == "__main__":
    main()
