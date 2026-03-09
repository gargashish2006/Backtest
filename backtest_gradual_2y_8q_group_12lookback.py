import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.structural_alpha_group_strategy import StructuralAlphaGroupStrategy

def run_gradual_group_12lookback():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup
    initial_total_capital = 100.0 
    scale_factor = 10000.0
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor
    
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    # Strategy Config: 30 stocks, 3 max per industry, Top 50% Groups, 12Q LOOKBACK (The Pinnacle)
    strategy = StructuralAlphaGroupStrategy(dh, num_stocks=30, max_per_industry=3, shareholder_lookback_quarters=12)
    
    # 2. Dates
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
    end_date = all_dates[-1] 
    
    # 3. Tranche Management
    tranche_qtys = {}
    bench_nav_history = []
    bench_units_total = 0.0
    
    current_q_idx = 0
    sim_dates = [d for d in all_dates if start_date <= d <= end_date]
    
    print(f"Starting Hierarchical 12Q Gradual Entry (30 stocks, Group-Filter, 12Q SL) from {start_date.date()}...")
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        portfolio.record_nav(date, prices)
        
        # Benchmark NAV
        bench_val = 0.0
        bench_df = getattr(dh, 'top_1000_bench', None)
        if bench_df is not None:
             b_data = bench_df[bench_df['date'] <= date]
             if not b_data.empty:
                b_current = b_data['index_value'].iloc[-1]
                bench_val = bench_units_total * b_current
        
        if current_q_idx < 8:
            bench_uninvested = (8 - current_q_idx) * q_allot
            bench_val += bench_uninvested
        bench_nav_history.append({'date': date, 'nav': bench_val})
        
        if date in rebalance_dates:
            current_q_idx += 1
            print(f"--- Quarter {current_q_idx}: {date.date()} ---")
            
            # Benchmark Step (12.5% x 8)
            if current_q_idx <= 8:
                if bench_df is not None:
                    b_data = bench_df[bench_df['date'] <= date]
                    if not b_data.empty:
                        b_current = b_data['index_value'].iloc[-1]
                        bench_units_total += q_allot / b_current
            
            # Strategy Step
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
                # 2-Year Rolling
                old_q_idx = current_q_idx - 8
                old_map = tranche_qtys.get(old_q_idx, {})
                
                if old_map:
                    print(f"Rolling 2-Year Tranche {old_q_idx}...")
                    for isin, orig_qty in old_map.items():
                        if isin in portfolio.holdings:
                            p = prices.get(isin)
                            if not p: p = portfolio.last_prices.get(isin, 0)
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

    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    df_bench = pd.DataFrame(bench_nav_history).set_index('date')
    
    final_nav = (portfolio.cash + portfolio.get_market_value(dh.get_daily_prices(df_nav.index[-1]))) / scale_factor
    final_bench = df_bench['nav'].iloc[-1] / scale_factor
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'] / scale_factor, label="Hierarchical 12Q Strategy (Top 50% Groups, 2Y Hold, 12Q lookback)")
    plt.plot(df_bench['nav'] / scale_factor, label="Staggered Benchmark (8Q Entry)", alpha=0.7, color='gray')
    plt.title(f"Hierarchical 12Q Strategy (The Pinnacle)\nStrategy: {final_nav:.1f} | Bench: {final_bench:.1f}")
    plt.ylabel("Portfolio Value (Base 100)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "gradual_2y_8q_group_12lookback_results.png")
    
    print(f"\nHIERARCHICAL 12Q SIMULATION COMPLETE")
    print(f"Final Strategy Value: {final_nav:.2f}")
    print(f"Final Benchmark Value: {final_bench:.2f}")

if __name__ == "__main__":
    run_gradual_group_12lookback()
