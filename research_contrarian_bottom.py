import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from strategies.structural_alpha_group_strategy import StructuralAlphaGroupStrategy

def run_simulation(dh, group_pct, filter_mode, scale_factor=10000.0):
    initial_total_capital = 100.0 
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor
    
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    strategy = StructuralAlphaGroupStrategy(dh, num_stocks=30, max_per_industry=3, 
                                            shareholder_lookback_quarters=8, 
                                            group_top_pct=group_pct,
                                            group_filter_mode=filter_mode)
    
    rebalance_dates = []
    for y in range(2019, 2025):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in dh.get_all_dates() if d >= dt]
            if avail:
                rebalance_dates.append(avail[0])
    
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    all_dates = dh.get_all_dates()
    start_date = rebalance_dates[0]
    sim_dates = [d for d in all_dates if start_date <= d <= all_dates[-1]]
    
    tranche_qtys = {}
    current_q_idx = 0
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            if current_q_idx <= 8:
                targets = strategy.calculate_selection(date)
                invest_val = q_allot
                tranche_map = {}
                for isin, weight in targets.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((invest_val * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            tranche_map[isin] = qty
                tranche_qtys[current_q_idx] = tranche_map
            else:
                old_q_idx = current_q_idx - 8
                old_map = tranche_qtys.get(old_q_idx, {})
                if old_map:
                    for isin, orig_qty in old_map.items():
                        if isin in portfolio.holdings:
                            p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                            fees = fee_model.calculate_costs(p * orig_qty, is_buy=False)
                            res = portfolio.sell(isin, date, p, orig_qty, fees)
                            tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                            portfolio.cash -= tax
                    investable = portfolio.cash * 0.98
                    targets = strategy.calculate_selection(date)
                    new_map = {}
                    for isin, weight in targets.items():
                        p = prices.get(isin)
                        if p:
                            qty = int((investable * weight) / (p * 1.0065))
                            if qty > 0:
                                fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                portfolio.buy(isin, date, p, qty, fees)
                                new_map[isin] = qty
                    tranche_qtys[current_q_idx] = new_map
    
    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def run_contrarian_test():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    print("Running Top 30% Groups (Alpha Engine)...")
    nav_top = run_simulation(dh, 0.3, 'top')
    
    print("Running Bottom 30% Groups (Contrarian Test)...")
    nav_bottom = run_simulation(dh, 0.3, 'bottom')
    
    # Benchmark
    bench_nav_history = []
    bench_units_total = 0.0
    initial_total_capital = 100.0
    scale_factor = 10000.0
    q_allot = 12.5 * scale_factor
    
    rebalance_dates = [d for d in dh.get_all_dates() if d.month in [2, 5, 8, 11] and d.day >= 15]
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    # Just a simple re-calc for standard staggered bench
    # (Actually I can just use the final values from walkthrough if needed)
    
    plt.figure(figsize=(12, 6))
    plt.plot(nav_top, label="Top 30% Groups (Conviction Alpha)", color='tab:green', linewidth=2)
    plt.plot(nav_bottom, label="Bottom 30% Groups (Contrarian/Least Cleaned)", color='tab:red', linewidth=2)
    plt.title(f"Contrarian Study: Top 30% vs Bottom 30% Groups (2Y Hold, 8Q SL)\nFinal Top: {nav_top.iloc[-1]:.1f} | Final Bottom: {nav_bottom.iloc[-1]:.1f}")
    plt.ylabel("Portfolio Value (Base 100)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    
    plot_path = repo_root / "contrarian_bottom_30_study.png"
    plt.savefig(plot_path)
    print(f"\nContrarian results: Top 30% ({nav_top.iloc[-1]:.2f}) vs Bottom 30% ({nav_bottom.iloc[-1]:.2f})")
    print(f"Plot saved to: {plot_path}")

if __name__ == "__main__":
    run_contrarian_test()
