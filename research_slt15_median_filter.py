import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

from strategies.slt15_strategy import SLT15Strategy
from strategies.slt15_median_filter_strategy import SLT15MedianFilterStrategy

def run_strategy_sim(dh, strategy_obj, hold_quarters, scale_factor=10000.0, start_date_str="2019-05-15"):
    initial_cash = 100.0 * scale_factor
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    
    for y in range(2019, 2026):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in all_dates if d >= dt]
            if avail: rebalance_dates.append(avail[0])
            
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date_str)]
    if not rebalance_dates: return pd.Series()
        
    start_date = rebalance_dates[0]
    sim_dates = [d for d in all_dates if start_date <= d <= all_dates[-1]]
    
    tranches = {}
    current_q_idx = 0
    q_allot = (initial_cash / hold_quarters)

    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue

        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            
            old_q = current_q_idx - hold_quarters
            if old_q in tranches:
                for isin, qty in tranches[old_q].items():
                    if isin in portfolio.holdings:
                        p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                        fees = fee_model.calculate_costs(p * qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                del tranches[old_q]
            
            selection = strategy_obj.calculate_selection(date)
            if selection:
                new_tranche = {}
                invest_val = portfolio.cash * 0.98 if current_q_idx > hold_quarters else q_allot
                
                for isin, weight in selection.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((invest_val * weight) / p)
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            new_tranche[isin] = qty
                if new_tranche:
                    tranches[current_q_idx] = new_tranche
                            
    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def calculate_metrics(nav_series):
    returns = nav_series.pct_change().dropna()
    cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (252 / len(nav_series)) - 1
    vol = returns.std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol > 0 else 0
    dd = (nav_series / nav_series.cummax() - 1).min()
    return {"CAGR": cagr, "Vol": vol, "Sharpe": sharpe, "MaxDD": dd, "Final NAV": nav_series.iloc[-1]}

def run_median_filter_compare():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    print("\nPre-loading Benchmark...")
    bench = dh.top_1000_bench.copy()
    bench['date'] = pd.to_datetime(bench['date'])
    bench = bench.set_index('date')['index_value']
    
    start_dt = pd.Timestamp("2019-05-15")
    bench = bench[bench.index >= start_dt]
    if not bench.empty:
        bench = bench / bench.iloc[0] * 100
        
    print("\nRunning SLT15_12Q Original (Breadth Filter)...")
    slt15_orig = SLT15Strategy(dh, lookback_quarters=12)
    nav_orig = run_strategy_sim(dh, slt15_orig, hold_quarters=8, start_date_str="2019-05-15")
    
    print("\nRunning SLT15_12Q Median (Median SH Decrease Filter)...")
    slt15_med = SLT15MedianFilterStrategy(dh, lookback_quarters=12)
    nav_med = run_strategy_sim(dh, slt15_med, hold_quarters=8, start_date_str="2019-05-15")
    
    # Trim to common period
    start_date = max(nav_orig.index[0], bench.index[0])
    nav_orig = nav_orig[nav_orig.index >= start_date] / nav_orig.iloc[0] * 100
    nav_med = nav_med[nav_med.index >= start_date] / nav_med.iloc[0] * 100
    bench = bench[bench.index >= start_date] / bench.iloc[0] * 100
    
    # Plotting
    plt.figure(figsize=(12, 7))
    plt.plot(nav_orig, label=f"SLT15_12Q Original [Breadth Filter] (NAV: {nav_orig.iloc[-1]:.1f})", color='navy', linewidth=2)
    plt.plot(nav_med, label=f"SLT15_12Q Variation [Median Filter] (NAV: {nav_med.iloc[-1]:.1f})", color='darkorange', linestyle='--', linewidth=2)
    plt.plot(bench, label="Top 1000", color='gray', linestyle=':', alpha=0.5)
    plt.title("SLT15_12Q Filter Logic: Breadth Rank vs Median SH Decrease Rank (May 2019 - Feb 2026)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = repo_root / "outputs/slt15_median_filter_comparison.png"
    plt.savefig(plot_path)
    print(f"\nComparison plot saved to: {plot_path}")
    
    # Metrics
    metrics = {
        "SLT15_12Q (Breadth Filter)": calculate_metrics(nav_orig),
        "SLT15_12Q (Median Filter)": calculate_metrics(nav_med),
        "Benchmark": calculate_metrics(bench)
    }
    
    df_metrics = pd.DataFrame(metrics).T
    print("\nInitial 35/35 Filtering Logic Comparison Metrics:")
    print(df_metrics[['Final NAV', 'CAGR', 'Sharpe', 'MaxDD']].to_string())

if __name__ == "__main__":
    run_median_filter_compare()
