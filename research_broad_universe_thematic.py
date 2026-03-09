import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_broad_universe_sim(dh, scale_factor=10000.0):
    initial_cash = 100.0 * scale_factor
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for y in range(2019, 2025):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in all_dates if d >= dt]
            if avail: rebalance_dates.append(avail[0])
            
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    start_date = rebalance_dates[0]
    sim_dates = [d for d in all_dates if start_date <= d <= all_dates[-1]]
    
    tranches = {}
    current_q_idx = 0
    q_allot = 12.5 * scale_factor
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            
            # 1. Shareholder Breadth (8Q) on TOTAL universe
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            if sh_trend.empty: 
                industry_winners = []
            else:
                # Universal stocks info (No top 1000 filter yet)
                stocks_info = []
                for isin in sh_trend['isin'].tolist():
                    if isin in dh.isin_to_group and isin in dh.isin_to_industry:
                        stocks_info.append({
                            'isin': isin,
                            'group': dh.isin_to_group[isin],
                            'industry': dh.isin_to_industry[isin],
                            'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0]
                        })
                
                if not stocks_info:
                    industry_winners = []
                else:
                    df_info = pd.DataFrame(stocks_info)
                    # 2. Group Top 35% (Universal)
                    group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
                    top_groups = group_stats.head(max(1, int(len(group_stats) * 0.35))).index.tolist()
                    
                    # 3. Industry Top 35% within Top Groups (Universal)
                    rel_df = df_info[df_info['group'].isin(top_groups)]
                    ind_stats = rel_df.groupby('industry')['decreased'].mean().sort_values(ascending=False)
                    industry_winners = ind_stats.head(max(1, int(len(ind_stats) * 0.35))).index.tolist()

            # --- EXIT LOGIC (8Q Lifecycle) ---
            old_q = current_q_idx - 8
            if old_q in tranches:
                for isin, qty in tranches[old_q].items():
                    if isin in portfolio.holdings:
                        p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                        fees = fee_model.calculate_costs(p * qty, is_buy=False)
                        res = portfolio.sell(isin, date, p, qty, fees)
                        tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                        portfolio.cash -= tax
                del tranches[old_q]
            
            # --- ENTRY LOGIC (New Tranche) ---
            if industry_winners:
                # 4. Filter for stocks in Top 1000 Market Cap
                univ = dh.get_universe(date, size=1000)
                univ_isins = set(univ['isin'].tolist())
                
                # Get the stocks belonging to winning industries that are in Top 1000
                selected_isins = [isin for isin in df_info[df_info['industry'].isin(industry_winners)]['isin'] if isin in univ_isins]
                
                if selected_isins:
                    new_tranche = {}
                    # Invest either the initial allotment or 1/8th of available cash
                    invest_val = q_allot if current_q_idx <= 8 else portfolio.cash * 0.98
                    w_per_stk = 1.0 / len(selected_isins)
                    
                    for isin in selected_isins:
                        p = prices.get(isin)
                        if p:
                            qty = int((invest_val * w_per_stk) / (p * 1.0065))
                            if qty > 0:
                                fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                portfolio.buy(isin, date, p, qty, fees)
                                new_tranche[isin] = qty
                    
                    if new_tranche:
                        tranches[current_q_idx] = new_tranche
                            
    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def run_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/my-backtesting-engine/analysis/outputs/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    print("Running Broad Universe Thematic Simulation (Total-to-Top1000)...")
    nav_model = run_broad_universe_sim(dh)
    
    # Benchmark Top 1000 EW
    bench = dh.top_1000_bench[dh.top_1000_bench['date'] >= nav_model.index[0]].copy()
    bench['nav'] = (bench['index_value'] / bench['index_value'].iloc[0]) * 100
    nav_bench = bench.set_index('date')['nav']
    
    print(f"Final NAV (Broad Univ Model): {nav_model.iloc[-1]:.2f}")
    print(f"Final NAV (Top 1000 Bench): {nav_bench.iloc[-1]:.2f}")
    
    plt.figure(figsize=(10, 6))
    nav_model.plot(label='Broad Universe Thematic (Top 35/35)')
    nav_bench.plot(label='Top 1000 Benchmark', alpha=0.7)
    plt.title("Broad Universe Thematic Selection vs Top 1000 Bench")
    plt.ylabel("Value (Base 100)")
    plt.legend()
    plt.grid(True)
    plt.savefig(repo_root / "broad_universe_thematic_nav.png")
    print("\nPlot saved to: broad_universe_thematic_nav.png")

if __name__ == "__main__":
    run_study()
