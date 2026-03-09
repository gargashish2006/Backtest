import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

# Import Strategies
from strategies.slt15_strategy import SLT15Strategy

def run_strategy_sim(dh, strategy_obj, hold_quarters, scale_factor=10000.0, start_date_str="2020-05-15"):
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
    if not rebalance_dates:
        print(f"No dates found after {start_date_str}")
        return pd.Series()
        
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
            
            # 1. Harvest expired tranche
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
            
            # 2. Deploy new tranche
            selection = strategy_obj.calculate_selection(date)
            if selection:
                new_tranche = {}
                # Simplified reinvestment:
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

def run_compare():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    print("Pre-loading Benchmark...")
    bench = dh.top_1000_bench.copy()
    bench['date'] = pd.to_datetime(bench['date'])
    bench = bench.set_index('date')['index_value']
    
    start_dt = pd.Timestamp("2019-05-15")
    bench = bench[bench.index >= start_dt]
    if not bench.empty:
        bench = bench / bench.iloc[0] * 100
    
    # 1. SLT15 (8Q hold)
    print("\nRunning SLT15 Baseline (8Q Lookback, 8Q Hold)...")
    slt15_8q = SLT15Strategy(dh, lookback_quarters=8)
    nav_8q = run_strategy_sim(dh, slt15_8q, hold_quarters=8, start_date_str="2019-05-15")
    
    # 2. SLT15 (12Q hold)
    print("\nRunning SLT15 Variation (12Q Lookback, 8Q Hold)...")
    slt15_12q = SLT15Strategy(dh, lookback_quarters=12)
    nav_12q = run_strategy_sim(dh, slt15_12q, hold_quarters=8, start_date_str="2019-05-15")
    
    # Trim to common period
    start_date = max(nav_8q.index[0], nav_12q.index[0], bench.index[0])
    nav_8q = nav_8q[nav_8q.index >= start_date]
    nav_12q = nav_12q[nav_12q.index >= start_date]
    bench = bench[bench.index >= start_date]
    
    bench = bench / bench.iloc[0] * 100
    nav_8q = nav_8q / nav_8q.iloc[0] * 100
    nav_12q = nav_12q / nav_12q.iloc[0] * 100
    
    # Plot
    plt.figure(figsize=(12, 7))
    plt.plot(nav_8q, label=f"SLT15 Baseline [8Q Lookback] (NAV: {nav_8q.iloc[-1]:.1f})", linewidth=2, color='navy')
    plt.plot(nav_12q, label=f"SLT15 Variation [12Q Lookback] (NAV: {nav_12q.iloc[-1]:.1f})", linewidth=2, color='darkorange')
    plt.plot(bench, label="Top 1000 Benchmark", color='gray', linestyle='--', alpha=0.7)
    plt.title("SLT15 Lookback Sensitivity: 8-Quarter vs 12-Quarter (May 2019 - Feb 2026)")
    plt.ylabel("Normalized NAV (Start = 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = repo_root / "outputs/slt15_8q_vs_12q.png"
    plt.savefig(plot_path)
    print(f"\nComparison plot saved to: {plot_path}")
    
    # Metrics
    metrics = {
        "SLT15 Baseline (8Q)": calculate_metrics(nav_8q),
        "SLT15 Variation (12Q)": calculate_metrics(nav_12q),
        "Benchmark": calculate_metrics(bench)
    }
    
    df_metrics = pd.DataFrame(metrics).T
    
    print("\nSLT15 Lookback Comparison Metrics (May 2019 - Feb 2026):")
    print(df_metrics[['Final NAV', 'CAGR', 'Sharpe', 'MaxDD']].to_string())

if __name__ == "__main__":
    run_compare()
