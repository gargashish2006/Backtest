import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.structural_alpha_strategy import StructuralAlphaStrategy

def run_staggered_structural():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 1. Setup
    initial_cash = 1000000.0
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    # Selection Strategy
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
    # tranches[i] = list of (isin, qty, buy_price)
    tranches = {} # quarter_idx -> list of isins
    tranche_original_qtys = {} # quarter_idx -> {isin: qty}
    
    current_q_idx = 0
    
    print(f"Starting Staggered Harvesting Simulation from {start_date.date()}...")
    
    for date in [d for d in all_dates if start_date <= d <= end_date]:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        
        # Daily Mark-to-Market
        portfolio.record_nav(date, prices)
        
        # Rebalance Logic
        if date in rebalance_dates:
            current_q_idx += 1
            print(f"--- Quarter {current_q_idx}: {date.date()} ---")
            
            # 1. Harvesting / Exit Phase
            if current_q_idx == 1:
                # FIRST REBALANCE: Invest 100%
                targets = strategy.calculate_selection(date)
                investable = portfolio.cash * 0.98
                
                tranche_qtys = {}
                for isin, weight in targets.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((investable * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            tranche_qtys[isin] = qty
                
                tranches[1] = list(targets.keys())
                tranche_original_qtys[1] = tranche_qtys
                
            elif 2 <= current_q_idx <= 4:
                # HARVEST 25% from Tranche 1
                harvest_cash = 0
                t1_qtys = tranche_original_qtys[1]
                
                for isin, orig_qty in t1_qtys.items():
                    p = prices.get(isin)
                    if not p: p = portfolio.last_prices.get(isin, 0)
                    
                    # Sell 25% of CURRENT holdings (not original)
                    # User: "Take out 25% from 1st portfolio"
                    # If we do 25%, 25%, 25% linearly:
                    sell_qty = int(orig_qty * 0.25)
                    if sell_qty > 0:
                        fees = fee_model.calculate_costs(p * sell_qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, sell_qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                
                # REINVEST into new Tranche
                investable = portfolio.cash * 0.98
                targets = strategy.calculate_selection(date)
                
                new_tranche_qtys = {}
                for isin, weight in targets.items():
                    p = prices.get(isin)
                    if p:
                        # Weight is relative to the NEW CASH
                        qty = int((investable * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            new_tranche_qtys[isin] = qty
                
                tranches[current_q_idx] = list(targets.keys())
                tranche_original_qtys[current_q_idx] = new_tranche_qtys
                
            else:
                # STEADY STATE (Q5 onwards)
                # Liquidate the OLD 1-year tranche
                # P1 (Q1) -> Exit remaining 25% in Q5
                # P2 (Q2) -> Exit 100% in Q6
                
                old_q_idx = current_q_idx - 4
                print(f"Exiting Tranche {old_q_idx} (1 Year Hold Complete)")
                
                # In Q5, P1 still has 25% left. Liquidate it.
                if old_q_idx == 1:
                    t1_qtys = tranche_original_qtys[1]
                    for isin in list(portfolio.holdings.keys()):
                        # We only want to sell stocks belonging to P1.
                        # Since we do FIFO, this is implicit IF we sell exactly what's left.
                        # However, for simplicity, let's just sell everything that remains of P1
                        p = prices.get(isin)
                        if not p: p = portfolio.last_prices.get(isin, 0)
                        
                        # Technically we should track which ISIN belongs to which tranche.
                        # But P1 contains specific ISINs. Let's sell the last 25% of any ISIN in P1 list.
                        if isin in t1_qtys:
                            # Sell whatever is left of the original quota
                            # (Some stocks might have been in multiple tranches, but FIFO handles this)
                            sell_qty = sum(lot.remaining_qty for lot in portfolio.holdings[isin] if (date - lot.buy_date).days > 300)
                            if sell_qty > 0:
                                fees = fee_model.calculate_costs(p * sell_qty, is_buy=False)
                                res = portfolio.sell(isin, date, p, sell_qty, fees)
                                tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                                portfolio.cash -= tax
                else:
                    # Pure 1-year exit for subsequent tranches
                    ti_qtys = tranche_original_qtys.get(old_q_idx, {})
                    for isin, orig_qty in ti_qtys.items():
                        if isin in portfolio.holdings:
                            p = prices.get(isin)
                            if not p: p = portfolio.last_prices.get(isin, 0)
                            
                            # Sell full qty of this tranche
                            sell_qty = orig_qty
                            fees = fee_model.calculate_costs(p * sell_qty, is_buy=False)
                            res = portfolio.sell(isin, date, p, sell_qty, fees)
                            tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                            portfolio.cash -= tax
                
                # REINVEST into new Tranche
                investable = portfolio.cash * 0.98
                targets = strategy.calculate_selection(date)
                
                new_tranche_qtys = {}
                for isin, weight in targets.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((investable * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            new_tranche_qtys[isin] = qty
                
                tranches[current_q_idx] = list(targets.keys())
                tranche_original_qtys[current_q_idx] = new_tranche_qtys

    # 4. Final Reporting
    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    final_nav = portfolio.cash + portfolio.get_market_value(dh.get_daily_prices(df_nav.index[-1]))
    total_ret = (final_nav / initial_cash) - 1
    
    # Benchmark
    bench = dh.top_1000_bench[(dh.top_1000_bench['date'] >= start_date) & 
                               (dh.top_1000_bench['date'] <= df_nav.index[-1])].copy()
    bench['norm_nav'] = bench['index_value'] / bench['index_value'].iloc[0] * initial_cash

    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'], label="Staggered Structural (1Y Hold Tranches)")
    plt.plot(bench['date'], bench['norm_nav'], label="Top 1000 EW Benchmark", alpha=0.6)
    plt.title(f"Staggered Structural Alpha (1Y Hold Rolling)\nNet Return: {total_ret:.1%}")
    plt.ylabel("Value (₹)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "staggered_structural_results.png")
    
    print(f"\nFinal Staggered NAV: ₹{final_nav:,.2f}")
    print(f"Total Net Return: {total_ret:.2%}")

if __name__ == "__main__":
    run_staggered_structural()
