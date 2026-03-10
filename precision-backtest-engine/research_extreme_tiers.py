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

def run_extreme_tiers():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    configs = [
        (0.2, 'top', 'Top 20% (Elite)'),
        (0.3, 'top', 'Top 30% (Conviction)'),
        (0.3, 'bottom', 'Bottom 30% (Noise)'),
        (0.2, 'bottom', 'Bottom 20% (Drain)')
    ]
    
    years = [2020, 2021, 2022, 2023, 2024]
    summary_results = []
    yearly_results = {}
    
    for pct, mode, label in configs:
        print(f"Running Hierarchical 8Q: {label}...")
        nav_series = run_simulation(dh, pct, mode)
        final_nav = nav_series.iloc[-1]
        summary_results.append({'Label': label, 'Final NAV': final_nav})
        
        # Extract Yearly
        y_rets = {}
        for y in years:
            y_start_data = nav_series[nav_series.index.year < y]
            y_end_data = nav_series[nav_series.index.year == y]
            if not y_start_data.empty and not y_end_data.empty:
                ret = (y_end_data.iloc[-1] / y_start_data.iloc[-1]) - 1
            else: ret = 0
            y_rets[y] = ret * 100
        yearly_results[label] = y_rets

    df_summary = pd.DataFrame(summary_results).set_index('Label')
    df_yearly = pd.DataFrame(yearly_results)
    
    print("\nEXTREME TIER SUMMARY (Final NAV):")
    print(df_summary.round(2))
    print("\nYEARLY PERFORMANCE BY TIER (%):")
    print(df_yearly.round(2))
    
    # Plot 1: Terminal Value
    plt.figure(figsize=(10, 6))
    colors = ['tab:green', 'tab:blue', 'tab:orange', 'tab:red']
    df_summary['Final NAV'].plot(kind='bar', color=colors)
    plt.title("The Alpha Funnel: Terminal Performance by Group Tier (Base 100)")
    plt.ylabel("Final Portfolio Value")
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "extreme_tiers_summary.png")
    
    # Plot 2: Yearly Comparison
    plt.figure(figsize=(12, 6))
    df_yearly.plot(kind='bar', ax=plt.gca(), width=0.8)
    plt.title("Yearly Alpha Decay: Top vs Bottom Tiers (%)")
    plt.ylabel("Annual Return (%)")
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "extreme_tiers_yearly.png")
    
    print(f"\nPlots saved to: extreme_tiers_summary.png and extreme_tiers_yearly.png")

if __name__ == "__main__":
    run_extreme_tiers()
