import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.structural_alpha_strategy import StructuralAlphaStrategy

def run_gradual_entry():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup
    initial_total_capital = 100.0 # Using 100 as base unit from user prompt
    quarterly_allocation = 25.0
    
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    
    # We'll use a larger absolute sum for decimals but keep the "100" scale for logic
    scale_factor = 10000.0 # So 100 -> 1,000,000 for realistic trade sizes
    initial_cash = initial_total_capital * scale_factor
    q_allot = quarterly_allocation * scale_factor
    
    portfolio = Portfolio(initial_cash=initial_cash)
    strategy = StructuralAlphaStrategy(dh, num_stocks=20, max_per_industry=4)
    
    # 2. Dates
    rebalance_dates = []
    for y in range(2019, 2024):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in dh.get_all_dates() if d >= dt]
            if avail:
                rebalance_dates.append(avail[0])
    
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    all_dates = dh.get_all_dates()
    start_date = rebalance_dates[0]
    end_date = pd.Timestamp("2023-12-31")
    
    # 3. Tranche Management
    # tranche_original_val[q_idx] = {isin: qty}
    tranche_qtys = {}
    
    # Benchmark Tracking (Separate "Shadow" Portfolio or just math)
    # Since benchmark is static after Q4, we track it manually
    bench_nav_history = []
    bench_holdings = {} # date_purchased -> {isin: qty} (though index is abstract, let's use Index units)
    # Unitized Benchmark Tracking: units = cash / index_value
    bench_units_total = 0.0
    
    current_q_idx = 0
    sim_dates = [d for d in all_dates if start_date <= d <= end_date]
    
    print(f"Starting Gradual Entry Simulation (25% x 4) from {start_date.date()}...")
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        # 1. Daily Mark-to-Market Strategy
        portfolio.record_nav(date, prices)
        
        # 2. Daily Benchmark NAV
        bench_val = 0.0
        # Get benchmark index value
        b_prices = dh.top_1000_bench[dh.top_1000_bench['date'] <= date]
        if not b_prices.empty:
            b_current = b_prices['index_value'].iloc[-1]
            bench_val = bench_units_total * b_current
        
        # Add uninvested benchmark cash (Q1-Q4)
        if current_q_idx < 4:
            bench_uninvested = (4 - current_q_idx) * q_allot
            bench_val += bench_uninvested
            
        bench_nav_history.append({'date': date, 'nav': bench_val})
        
        # 3. Rebalance Logic
        if date in rebalance_dates:
            current_q_idx += 1
            print(f"--- Quarter {current_q_idx}: {date.date()} ---")
            
            # BENCHMARK TRADING (Q1-Q4)
            if current_q_idx <= 4:
                b_current = dh.top_1000_bench[dh.top_1000_bench['date'] <= date]['index_value'].iloc[-1]
                # "Buy" 25 units of benchmark index
                new_bench_units = q_allot / b_current
                bench_units_total += new_bench_units
            
            # STRATEGY TRADING
            if current_q_idx <= 4:
                # ENTRY PHASE: Invest 25 each time
                targets = strategy.calculate_selection(date)
                # We use exactly q_allot for this tranche
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
                # REINVESTMENT PHASE: Liquidate oldest (1Y) and reinvest
                old_q_idx = current_q_idx - 4
                old_map = tranche_qtys.get(old_q_idx, {})
                print(f"Rolling Old Tranche {old_q_idx}...")
                
                # Exit all from that tranche
                reinvest_cash = 0
                for isin, orig_qty in old_map.items():
                    if isin in portfolio.holdings:
                        p = prices.get(isin)
                        if not p: p = portfolio.last_prices.get(isin, 0)
                        
                        # FIFO Sale: sell the oldest units
                        fees = fee_model.calculate_costs(p * orig_qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, orig_qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                
                # Current cash in portfolio now includes the liquidated tranche proceeds
                # We need to calculate how much of the portfolio's cash came from THIS liquidation 
                # to strictly follow "re-invest from the 1 rebalance portfolio".
                # For simplicity, we assume all current cash (which was mostly just the liquidated proceeds) is reinvested.
                # In this engine, cash is shared, but since rebalances happen once per Q, the cash is mostly static.
                
                investable = portfolio.cash * 0.98 # Keep buffer
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

    # 4. Final Reporting
    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    df_bench = pd.DataFrame(bench_nav_history).set_index('date')
    
    final_p_prices = dh.get_daily_prices(df_nav.index[-1])
    final_nav = portfolio.cash + portfolio.get_market_value(final_p_prices)
    final_bench = df_bench['nav'].iloc[-1]
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'] / scale_factor, label="Strategy (Gradual Entry 25x4)", linewidth=2)
    plt.plot(df_bench['nav'] / scale_factor, label="Benchmark (Gradual then Static)", alpha=0.7)
    plt.title(f"Gradual Entry Comparison: Strategy vs Staggered Benchmark\nStrategy: {final_nav/scale_factor:.1f} | Bench: {final_bench/scale_factor:.1f}")
    plt.ylabel("Portfolio Value (Base 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "gradual_entry_results.png")
    
    print(f"\nGRADUAL ENTRY COMPLETE")
    print(f"Final Strategy Value: {final_nav/scale_factor:.2f}")
    print(f"Final Benchmark Value: {final_bench/scale_factor:.2f}")
    print(f"Strategy Return (on 100 base): {(final_nav/scale_factor - 100):.2f}%")
    print(f"Benchmark Return (on 100 base): {(final_bench/scale_factor - 100):.2f}%")

if __name__ == "__main__":
    run_gradual_entry()
