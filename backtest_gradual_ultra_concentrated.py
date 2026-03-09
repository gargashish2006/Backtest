import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.structural_alpha_strategy import StructuralAlphaStrategy

def run_gradual_ultra_concentrated():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup
    initial_total_capital = 100.0 
    scale_factor = 10000.0
    initial_cash = initial_total_capital * scale_factor
    q_allot = 25.0 * scale_factor
    
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    # Strategy Config: Top 5 Industries, 1 stock each
    strategy = StructuralAlphaStrategy(dh, num_stocks=5, max_per_industry=1)
    
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
    tranche_qtys = {}
    bench_nav_history = []
    bench_units_total = 0.0
    
    current_q_idx = 0
    sim_dates = [d for d in all_dates if start_date <= d <= end_date]
    
    print(f"Starting Ultra-Concentrated Gradual Entry (5 stocks, 25% x 4) from {start_date.date()}...")
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        # Daily Strategy NAV
        portfolio.record_nav(date, prices)
        
        # Daily Benchmark NAV (Static after Q4)
        bench_val = 0.0
        b_prices = dh.top_1000_bench[dh.top_1000_bench['date'] <= date]
        if not b_prices.empty:
            b_current = b_prices['index_value'].iloc[-1]
            bench_val = bench_units_total * b_current
        
        if current_q_idx < 4:
            bench_uninvested = (4 - current_q_idx) * q_allot
            bench_val += bench_uninvested
        bench_nav_history.append({'date': date, 'nav': bench_val})
        
        # Rebalance
        if date in rebalance_dates:
            current_q_idx += 1
            print(f"--- Quarter {current_q_idx}: {date.date()} ---")
            
            # Benchmark Step
            if current_q_idx <= 4:
                b_current = dh.top_1000_bench[dh.top_1000_bench['date'] <= date]['index_value'].iloc[-1]
                bench_units_total += q_allot / b_current
            
            # Strategy Step
            if current_q_idx <= 4:
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
                old_q_idx = current_q_idx - 4
                old_map = tranche_qtys.get(old_q_idx, {})
                
                # Liquidate
                for isin, orig_qty in old_map.items():
                    if isin in portfolio.holdings:
                        p = prices.get(isin)
                        if not p: p = portfolio.last_prices.get(isin, 0)
                        
                        fees = fee_model.calculate_costs(p * orig_qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, orig_qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                
                # Reinvest
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

    # Final Report
    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    df_bench = pd.DataFrame(bench_nav_history).set_index('date')
    
    final_nav = (portfolio.cash + portfolio.get_market_value(dh.get_daily_prices(df_nav.index[-1]))) / scale_factor
    final_bench = df_bench['nav'].iloc[-1] / scale_factor
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'] / scale_factor, label="Ultra-Concentrated (5 stocks, Top 5 Ind)")
    plt.plot(df_bench['nav'] / scale_factor, label="Staggered Benchmark (Static)", alpha=0.7)
    plt.title(f"Ultra-Concentrated Gradual Entry: Top 5 Industries\nStrategy: {final_nav:.1f} | Bench: {final_bench:.1f}")
    plt.ylabel("Portfolio Value (Base 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "gradual_ultra_concentrated_results.png")
    
    print(f"\nULTRA-CONCENTRATED GRADUAL ENTRY COMPLETE")
    print(f"Final Strategy Value: {final_nav:.2f}")
    print(f"Final Benchmark Value: {final_bench:.2f}")

if __name__ == "__main__":
    run_gradual_ultra_concentrated()
