import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from strategies.slt15_strategy import SLT15Strategy

def run_slt15_sim(dh, dynamic_exit=False, hold_quarters=8, scale_factor=10000.0):
    initial_cash = 100.0 * scale_factor
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    strategy = SLT15Strategy(dh)
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

    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            
            # --- Thesis Breach Exit ---
            if dynamic_exit:
                qualified_industries = strategy.get_qualified_industries(date)
                to_sell_breach = []
                for isin in portfolio.holdings.keys():
                    ind = dh.isin_to_industry.get(isin)
                    if ind not in qualified_industries:
                        to_sell_breach.append(isin)
                
                for isin in to_sell_breach:
                    p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                    if p > 0:
                        qty = sum(lot.remaining_qty for lot in portfolio.holdings[isin])
                        fees = fee_model.calculate_costs(p * qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                        
                        # Remove from tranches
                        for q_idx in list(tranches.keys()):
                            if isin in tranches[q_idx]:
                                del tranches[q_idx][isin]

            # --- 1. Harvest expired tranche (Only for tranches that survived breach exit) ---
            old_q = current_q_idx - hold_quarters
            if old_q in tranches:
                for isin, qty in list(tranches[old_q].items()):
                    if isin in portfolio.holdings:
                        p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                        if p > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=False)
                            res = portfolio.sell(isin, date, p, qty, fees)
                            tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                            portfolio.cash -= tax
                del tranches[old_q]
            
            # --- 2. Deploy new tranche ---
            selection = strategy.calculate_selection(date)
            if selection:
                new_tranche = {}
                # Deploy 1/N of current cash to keep it simple and reinvesting the breched amount
                n_active_slots = len([t for t in tranches if t > current_q_idx - hold_quarters])
                slots_remaining = hold_quarters - n_active_slots
                invest_val = portfolio.cash * 0.98 / max(1, slots_remaining)
                
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

def run_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    print("Running SLT15 Baseline (Passive 2Y Hold)...")
    nav_passive = run_slt15_sim(dh, dynamic_exit=False)
    
    print("Running SLT15 Dynamic (Thesis Breach Exit)...")
    nav_dynamic = run_slt15_sim(dh, dynamic_exit=True)
    
    bench = dh.top_1000_bench.set_index('date')['index_value']
    bench = bench[bench.index >= nav_passive.index[0]]
    bench = bench / bench.iloc[0] * 100
    
    nav_passive = nav_passive / nav_passive.iloc[0] * 100
    nav_dynamic = nav_dynamic / nav_dynamic.iloc[0] * 100
    
    plt.figure(figsize=(12, 7))
    plt.plot(nav_passive, label=f"SLT15 Passive (NAV: {nav_passive.iloc[-1]:.1f})", color='navy', alpha=0.7)
    plt.plot(nav_dynamic, label=f"SLT15 Dynamic Exit (NAV: {nav_dynamic.iloc[-1]:.1f})", color='red', linewidth=2)
    plt.plot(bench, label="Top 1000 Benchmark", color='gray', linestyle='--', alpha=0.5)
    plt.title("SLT15 Sensitivity: Passive 2Y vs Dynamic Industry Exit")
    plt.ylabel("NAV (Start=100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = repo_root / "outputs/slt15_dynamic_exit_study.png"
    plt.savefig(plot_path)
    print(f"Study plot saved to: {plot_path}")
    
    metrics = {
        "SLT15 Passive": calculate_metrics(nav_passive),
        "SLT15 Dynamic": calculate_metrics(nav_dynamic),
        "Benchmark": calculate_metrics(bench)
    }
    df_metrics = pd.DataFrame(metrics).T
    print("\nStudy Metrics Head-to-Head:")
    print(df_metrics[['Final NAV', 'CAGR', 'Sharpe', 'MaxDD']].to_string())

if __name__ == "__main__":
    run_study()
