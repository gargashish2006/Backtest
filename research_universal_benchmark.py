import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_universal_simulation(dh, universe_size=1000, scale_factor=10000.0):
    initial_total_capital = 100.0 
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor  # 1/8th of capital per rebalance
    
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
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
            # Get Top 1000 universe
            targets_df = dh.get_universe(date, size=universe_size)
            targets = targets_df['isin'].tolist()
            num_targets = len(targets)
            
            if current_q_idx <= 8:
                invest_val = q_allot
                weight = 1.0 / num_targets if num_targets > 0 else 0
                tranche_map = {}
                for isin in targets:
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
                
                investable = portfolio.cash * 0.98  # Buffer for fees
                weight = 1.0 / num_targets if num_targets > 0 else 0
                new_map = {}
                for isin in targets:
                    p = prices.get(isin)
                    if p:
                        qty = int((investable * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            new_map[isin] = qty
                tranche_qtys[current_q_idx] = new_map
    
    nav_series = pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor
    return nav_series

def run_universal_discovery():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    print("Running Universal Uncapped Simulation (All Top 1000 Stocks)...")
    nav_universal = run_universal_simulation(dh)
    
    print(f"Final NAV (Universal Top 1000): {nav_universal.iloc[-1]:.2f}")
    
    # Extract Yearly
    years = [2020, 2021, 2022, 2023, 2024]
    y_rets = {}
    for y in years:
        y_start_data = nav_universal[nav_universal.index.year < y]
        y_end_data = nav_universal[nav_universal.index.year == y]
        if not y_start_data.empty and not y_end_data.empty:
            ret = (y_end_data.iloc[-1] / y_start_data.iloc[-1]) - 1
        else: ret = 0
        y_rets[y] = ret * 100
        
    print("\nYEARLY PERFORMANCE (Universal) (%):")
    for y, r in y_rets.items():
        print(f"{y}: {r:.2f}%")
        
    # Plotting
    plt.figure(figsize=(10, 6))
    nav_universal.plot(label='Universal (Top 1000 Uncapped)', color='gray')
    plt.title("Universal Unlimited Portfolio: Top 1000 Universe (NAV)")
    plt.ylabel("Portfolio Value (Base 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "universal_uncapped_nav.png")
    
    print(f"\nPlot saved to: universal_uncapped_nav.png")

if __name__ == "__main__":
    run_universal_discovery()
