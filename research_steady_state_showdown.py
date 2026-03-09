import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

# Import Strategies
from strategies.cs15_strategy import CS15Strategy
from strategies.mcps15_strategy import MCPSStrategy
from strategies.slt15_strategy import SLT15Strategy

def run_strategy_sim(dh, strategy_obj, hold_quarters, scale_factor=10000.0):
    initial_cash = 100.0 * scale_factor
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for y in range(2019, 2027):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in all_dates if d >= dt]
            if avail: rebalance_dates.append(avail[0])
            
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    start_date = rebalance_dates[0]
    sim_dates = [d for d in all_dates if start_date <= d <= all_dates[-1]]
    
    tranches = {}
    current_q_idx = 0
    q_allot = (initial_cash / hold_quarters)
    
    # Pre-compute RSI if needed
    if hasattr(strategy_obj, 'precompute_rsi'):
        strategy_obj.precompute_rsi(sim_dates)

    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        if hasattr(strategy_obj, 'check_exits'):
            to_sell = strategy_obj.check_exits(date, portfolio.holdings)
            for isin in to_sell:
                p = prices.get(isin)
                if p:
                    qty = sum(lot.remaining_qty for lot in portfolio.holdings[isin])
                    fees = fee_model.calculate_costs(p * qty, is_buy=False)
                    res = portfolio.sell(isin, date, p, qty, fees)
                    tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                    portfolio.cash -= tax

        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            old_q = current_q_idx - hold_quarters
            if old_q in tranches:
                for isin, qty in list(tranches[old_q].items()):
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

def run_steady_state_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    print("Pre-loading Benchmark...")
    bench = dh.top_1000_bench.set_index('date')['index_value']
    print("Running SLT15 (Steady State Audit - 8Q Staggered)...")
    slt15 = SLT15Strategy(dh)
    nav_slt = run_strategy_sim(dh, slt15, hold_quarters=8)
    
    print("Running MCPS12 (Steady State Audit - Quarterly Rebalance)...")
    mcps = MCPSStrategy(dh, num_stocks=12)
    nav_mcps = run_strategy_sim(dh, mcps, hold_quarters=1)
    
    print("Running CS15 (Steady State Audit - Quarterly Rebalance)...")
    cs15 = CS15Strategy(dh)
    nav_cs = run_strategy_sim(dh, cs15, hold_quarters=1)
    
    # Define Steady State Start: Feb 15, 2021 (All are fully deployed)
    steady_date = pd.Timestamp("2021-02-15")
    actual_steady_date = min([d for d in nav_slt.index if d >= steady_date])
    
    nav_slt = nav_slt[nav_slt.index >= actual_steady_date]
    nav_mcps = nav_mcps[nav_mcps.index >= actual_steady_date]
    nav_cs = nav_cs[nav_cs.index >= actual_steady_date]
    bench = bench[bench.index >= actual_steady_date]
    
    # Normalize to 100 on steady_date
    nav_slt = nav_slt / nav_slt.iloc[0] * 100
    nav_mcps = nav_mcps / nav_mcps.iloc[0] * 100
    nav_cs = nav_cs / nav_cs.iloc[0] * 100
    bench = bench / bench.iloc[0] * 100
    
    plt.figure(figsize=(12, 7))
    plt.plot(nav_slt, label=f"SLT15 (NAV: {nav_slt.iloc[-1]:.1f})", color='navy', linewidth=2)
    plt.plot(nav_mcps, label=f"MCPS12 (NAV: {nav_mcps.iloc[-1]:.1f})", color='darkgreen', alpha=0.7)
    plt.plot(nav_cs, label=f"CS15 (NAV: {nav_cs.iloc[-1]:.1f})", color='darkorange', alpha=0.7)
    plt.plot(bench, label="Top 1000 Benchmark", color='gray', linestyle='--', alpha=0.5)
    plt.title("Steady-State Champion Showdown (Start = Feb 2021)")
    plt.ylabel("Asset Growth (Normalized to 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = repo_root / "outputs/slt15_steady_state_showdown.png"
    plt.savefig(plot_path)
    print(f"Study plot saved to: {plot_path}")
    
    metrics = {
        "SLT15 (Steady)": calculate_metrics(nav_slt),
        "MCPS12 (Steady)": calculate_metrics(nav_mcps),
        "CS15 (Steady)": calculate_metrics(nav_cs),
        "Benchmark": calculate_metrics(bench)
    }
    df_metrics = pd.DataFrame(metrics).T
    print("\nSteady-State Metrics (Feb 2021 - Feb 2026):")
    print(df_metrics[['Final NAV', 'CAGR', 'Sharpe', 'MaxDD']].to_string())

if __name__ == "__main__":
    run_steady_state_study()
