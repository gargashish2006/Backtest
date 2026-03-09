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
    for y in range(2019, 2026):
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
    
    # Pre-compute RSI if needed (for CS15/MCPS)
    if hasattr(strategy_obj, 'precompute_rsi'):
        strategy_obj.precompute_rsi(sim_dates)

    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        # Daily Exits (CS15/MCPS might have them)
        if hasattr(strategy_obj, 'check_exits'):
            to_sell = strategy_obj.check_exits(date, portfolio.holdings)
            for isin in to_sell:
                p = prices.get(isin)
                if p:
                    # Index into the lots list and sum quantities
                    qty = sum(lot.remaining_qty for lot in portfolio.holdings[isin])
                    fees = fee_model.calculate_costs(p * qty, is_buy=False)
                    res = portfolio.sell(isin, date, p, qty, fees)
                    tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                    portfolio.cash -= tax

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
                invest_val = q_allot if current_q_idx <= hold_quarters else (portfolio.cash * 0.98 / (hold_quarters - len([t for t in tranches if t > current_q_idx - hold_quarters])))
                # Simplified reinvestment: just use 1/N of total cash for the new slot
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

def run_showdown():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    print("Pre-loading Benchmark...")
    bench = dh.top_1000_bench.copy()
    bench['date'] = pd.to_datetime(bench['date'])
    bench = bench.set_index('date')['index_value']
    bench = bench / bench.iloc[0] * 100
    
    # 1. SLT15 (8Q hold)
    print("Running SLT15 (2Y Hold)...")
    slt15 = SLT15Strategy(dh)
    nav_slt = run_strategy_sim(dh, slt15, hold_quarters=8)
    
    # 2. MCPS12 (4Q hold)
    print("Running MCPS12 (1Y Hold)...")
    mcps = MCPSStrategy(dh, num_stocks=12)
    nav_mcps = run_strategy_sim(dh, mcps, hold_quarters=4)
    
    # 3. CS15 (4Q hold)
    print("Running CS15 (1Y Hold)...")
    cs15 = CS15Strategy(dh)
    nav_cs = run_strategy_sim(dh, cs15, hold_quarters=4)
    
    # Trim to common period
    start_date = max(nav_slt.index[0], nav_mcps.index[0], nav_cs.index[0])
    nav_slt = nav_slt[nav_slt.index >= start_date]
    nav_mcps = nav_mcps[nav_mcps.index >= start_date]
    nav_cs = nav_cs[nav_cs.index >= start_date]
    bench = bench[bench.index >= start_date]
    bench = bench / bench.iloc[0] * 100
    nav_slt = nav_slt / nav_slt.iloc[0] * 100
    nav_mcps = nav_mcps / nav_mcps.iloc[0] * 100
    nav_cs = nav_cs / nav_cs.iloc[0] * 100
    
    # Plot
    plt.figure(figsize=(12, 7))
    plt.plot(nav_slt, label=f"SLT15 (NAV: {nav_slt.iloc[-1]:.1f})", linewidth=2, color='navy')
    plt.plot(nav_mcps, label=f"MCPS12 (NAV: {nav_mcps.iloc[-1]:.1f})", linewidth=1.5, color='darkgreen')
    plt.plot(nav_cs, label=f"CS15 (NAV: {nav_cs.iloc[-1]:.1f})", linewidth=1.5, color='darkorange')
    plt.plot(bench, label="Top 1000 Benchmark", color='gray', linestyle='--', alpha=0.7)
    plt.title("Champion Showdown: CS15 vs MCPS12 vs SLT15 (Net Returns)")
    plt.ylabel("Normalized NAV (Start = 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = repo_root / "outputs/champion_showdown.png"
    plt.savefig(plot_path)
    print(f"Comparison plot saved to: {plot_path}")
    
    # Metrics
    metrics = {
        "SLT15": calculate_metrics(nav_slt),
        "MCPS12": calculate_metrics(nav_mcps),
        "CS15": calculate_metrics(nav_cs),
        "Benchmark": calculate_metrics(bench)
    }
    
    df_metrics = pd.DataFrame(metrics).T
    df_metrics['CAGR'] = (df_metrics['CAGR'] * 100).round(2).astype(str) + "%"
    df_metrics['MaxDD'] = (df_metrics['MaxDD'] * 100).round(2).astype(str) + "%"
    df_metrics['Sharpe'] = df_metrics['Sharpe'].round(2)
    df_metrics['Final NAV'] = df_metrics['Final NAV'].round(2)
    
    print("\nChampion Showdown Metrics:")
    print(df_metrics[['Final NAV', 'CAGR', 'Sharpe', 'MaxDD']].to_string())

if __name__ == "__main__":
    run_showdown()
