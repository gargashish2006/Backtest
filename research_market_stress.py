import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def run_stress_signal_research():
    print("Loading Data...")
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Dates to analyze
    # Bad Periods (Drawdowns)
    bad_dates = [
        pd.Timestamp("2020-02-14"), # Covid Crash Start
        pd.Timestamp("2021-08-13"), # Mid-2021
        pd.Timestamp("2021-11-15"), # 2021 Top/Correction
        pd.Timestamp("2024-11-14"), # Recent Drawdown
    ]
    # Good Periods (Rallies for comparison)
    good_dates = [
        pd.Timestamp("2020-11-14"), # Post-Covid Rally
        pd.Timestamp("2023-05-15"), # 2023 Bull Run
        pd.Timestamp("2017-08-14"), # Early Bull
    ]

    all_target_dates = sorted(bad_dates + good_dates)
    
    # Initialize basic strategy for reusing helper methods
    strategy = ContrarianBreadthStrategy(dh, num_stocks=15)

    print("\n" + "="*140)
    print(f"{'Date':<12} | {'Type':<6} | {'Univ Size':<9} | {'% > 200SMA':<10} | {'Avg SH Decr':<11} | {'% Ind Qualify':<13} | {'Avg RSNP':<8} | {'Bench Returns (1y)':<18}")
    print("-" * 140)

    for date in all_target_dates:
        date_type = "BAD" if date in bad_dates else "GOOD"
        
        # 1. Setup Logic Dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = dh.get_all_dates()
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])

        # 2. Universe (Top 1000)
        metrics = dh.get_daily_metrics(actual_calc_date)
        if metrics.empty:
            print(f"{date.date()} | NO DATA")
            continue
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        univ_isins = universe['isin'].tolist()

        # 3. Market Breadth: % > 200 SMA
        # Get prices for last 205 days to compute 200 SMA
        window_start = actual_calc_date - pd.Timedelta(days=350) # generous buffer
        window_dates = [d for d in all_dates if window_start <= d <= actual_calc_date]
        # We need efficient lookup. Let's just get the last 200 days for each isin
        # DataHandler doesn't have a vectorized 'get_sma' helper exposed easily, 
        # but we can do a bulk fetch.
        
        # Strategy: Get prices for universe for last 200 trading days
        # This might be slow if we do it one by one. 
        # Optimization: use dh.price_df directly.
        
        # Filter price_df for universe and window
        recent_prices = dh.price_df[
            (dh.price_df['isin'].isin(univ_isins)) & 
            (dh.price_df['date'].isin(window_dates))
        ].copy()
        
        # Calculate percent > 200 SMA
        above_sma_count = 0
        valid_count = 0
        
        # Group by ISIN and check
        # We need exactly the last price date (actual_calc_date) and the 200-day avg
        # A quick way:
        grouped = recent_prices.sort_values('date').groupby('isin')['close']
        
        # Check current price vs rolling mean
        # This is heavy. Let's do a simpler check via pandas last() and mean()
        # Note: this approximation assumes the window is roughly 200 trading days.
        # 200 trading days ~ 290 calendar days. 
        # precise 200 d window:
        lookup_window = window_dates[-200:]
        subset_200 = recent_prices[recent_prices['date'].isin(lookup_window)]
        
        means = subset_200.groupby('isin')['close'].mean()
        lasts = subset_200.groupby('isin')['close'].last()
        
        # Align
        aligned = pd.concat([means, lasts], axis=1, keys=['mean', 'last']).dropna()
        if not aligned.empty:
            above_count = (aligned['last'] > aligned['mean']).sum()
            total = len(aligned)
            pct_above_200 = above_count / total
        else:
            pct_above_200 = 0.0

        # 4. Shareholder Breath
        sh_trend = dh.get_shareholder_trend(date, lookback_quarters=4)
        avg_sh_decr = 0
        pct_ind_qualify = 0
        
        if not sh_trend.empty:
            # Overall "Contrarian-ness" of the market
            # What % of the universe has decreased shareholders?
            sh_trend_univ = sh_trend[sh_trend['isin'].isin(univ_isins)]
            avg_sh_decr = sh_trend_univ['decreased'].mean() # This is basically "% with decrease" since 'decreased' is 0 or 1
            
            # % of Industries that qualify the 50% threshold
            sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
            ind_stats = sh_trend.groupby('industry')['decreased'].mean()
            qualifying = ind_stats[ind_stats >= 0.50]
            pct_ind_qualify = len(qualifying) / len(ind_stats) if len(ind_stats) > 0 else 0

        # 5. RSNP (Benchmark Relative Strength)
        # Bench Return
        b_prices = dh.top_1000_bench
        b_end = b_prices[b_prices['date'] <= actual_calc_date]['index_value'].iloc[-1]
        b_start = b_prices[b_prices['date'] <= actual_lookback_start]['index_value'].iloc[-1]
        bench_ret = (b_end / b_start) - 1
        
        # Only check RSNP for "Qualified" industries to see if they are weak
        # Re-using logic from strategy to get qualified industries
        # Simplified: Just grab the industries that passed the 50% relative / 50% abs filter
        # sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
        # grp_stats = sh_trend.groupby('group')['decreased'].mean()
        # top_grps = grp_stats.sort_values(ascending=False).head(int(len(grp_stats)*0.5)).index.tolist()
        # valid_inds = sh_trend[sh_trend['group'].isin(top_grps)].groupby('industry')['decreased'].mean()
        # final_inds = valid_inds[valid_inds >= 0.5].index.tolist()
        
        # Compute RSNP for these final industries
        # We can reuse the result from earlier steps if we had them, but let's just do a proxy:
        # What is the AVERAGE RSNP of the top 10 potential industries?
        
        # Fast pivot for price
        p_window = [d for d in all_dates if d <= actual_calc_date][-30:]
        p_subset = dh.price_df[dh.price_df['date'].isin(p_window)]
        p_end_map = p_subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        start_window = [d for d in all_dates if d <= actual_lookback_start][-30:]
        s_subset = dh.price_df[dh.price_df['date'].isin(start_window)]
        p_start_map = s_subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        rsnp_values = []
        # Calculate RSNP for ALL industries to get a market-wide view
        all_industries = sh_trend['industry'].unique()
        for ind in all_industries:
            isins = [i for i, n in dh.isin_to_industry.items() if n == ind]
            wins, eligible = 0, 0
            for i in isins:
                p1, p0 = p_end_map.get(i), p_start_map.get(i)
                if p1 and p0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_ret: wins += 1
            if eligible >= 5: # min size
                rsnp_values.append(wins/eligible)
        
        avg_rsnp = np.mean(rsnp_values) if rsnp_values else 0

        print(f"{date.strftime('%Y-%m-%d'):<12} | {date_type:<6} | {len(univ_isins):<9} | {pct_above_200:<10.2%} | {avg_sh_decr:<11.2%} | {pct_ind_qualify:<13.2%} | {avg_rsnp:<8.2f} | {bench_ret:<18.2%}")

    print("="*140)

if __name__ == "__main__":
    run_stress_signal_research()
