import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from strategies.structural_alpha_strategy import StructuralAlphaStrategy
from strategies.structural_alpha_group_strategy import StructuralAlphaGroupStrategy

def run_simulation(dh, strategy_obj, scale_factor=10000.0):
    initial_total_capital = 100.0 
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor
    
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
            if current_q_idx <= 8:
                targets = strategy_obj.calculate_selection(date)
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
                    targets = strategy_obj.calculate_selection(date)
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

def run_comparison():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Strategies
    strat_hier_8q = StructuralAlphaGroupStrategy(dh, num_stocks=30, max_per_industry=3, shareholder_lookback_quarters=8)
    strat_std_12q = StructuralAlphaStrategy(dh, num_stocks=30, max_per_industry=3, shareholder_lookback_quarters=12)
    
    print("Running Hierarchical 8Q...")
    nav_hier = run_simulation(dh, strat_hier_8q)
    
    print("Running Standard 12Q...")
    nav_std = run_simulation(dh, strat_std_12q)
    
    # 2. Results Extraction
    results = []
    years = [2020, 2021, 2022, 2023, 2024]
    
    for y in years:
        # Hierarchical Returns
        h_start = nav_hier[nav_hier.index.year < y]
        h_end = nav_hier[nav_hier.index.year == y]
        if not h_start.empty and not h_end.empty:
            h_ret = (h_end.iloc[-1] / h_start.iloc[-1]) - 1
        else: h_ret = 0
        
        # Standard Returns
        s_start = nav_std[nav_std.index.year < y]
        s_end = nav_std[nav_std.index.year == y]
        if not s_start.empty and not s_end.empty:
            s_ret = (s_end.iloc[-1] / s_start.iloc[-1]) - 1
        else: s_ret = 0
        
        results.append({
            'Year': y,
            'Hierarchical 8Q (%)': h_ret * 100,
            'Standard 12Q (%)': s_ret * 100
        })
        
    df = pd.DataFrame(results).set_index('Year')
    print("\nYEAR-BY-YEAR COMPARISON:")
    print(df.round(2))
    
    # 3. Plotting
    ax = df.plot(kind='bar', figsize=(10, 6), width=0.8)
    plt.title("Year-by-Year Performance Comparison\nHierarchical 8Q vs Standard 12Q")
    plt.ylabel("Annual Return (%)")
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plot_path = repo_root / "yearly_comparison_8q_vs_12q.png"
    plt.savefig(plot_path)
    print(f"\nPlot saved to: {plot_path}")

if __name__ == "__main__":
    run_comparison()
