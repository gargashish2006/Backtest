import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_contrarian_rsnp_simulation(dh, scale_factor=10000.0):
    initial_total_capital = 100.0 
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor  # 1/8th per rebalance
    
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
            
            # 1. Shareholder Breadth (8Q)
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            if sh_trend.empty: continue
            
            # 2. Universe (Top 1000)
            univ = dh.get_universe(date, size=1000)
            univ_isins = set(univ['isin'].tolist())
            
            # 3. Benchmark Data for RSNP (using Top 1000 median as benchmark proxy)
            # Or use a slightly earlier date for lookback (e.g. 1 quarter ago)
            quarter_ago_date = max([d for d in all_dates if d <= date - pd.Timedelta(days=90)])
            prev_prices = dh.get_daily_prices(quarter_ago_date)
            
            common_isins = set(prices.keys()).intersection(set(prev_prices.keys())).intersection(univ_isins)
            bench_returns = {isin: (prices[isin]/prev_prices[isin]) - 1 for isin in common_isins}
            bench_median = pd.Series(list(bench_returns.values())).median()
            
            stocks_with_info = []
            for isin in common_isins:
                if isin in dh.isin_to_group and isin in dh.isin_to_industry:
                    stocks_with_info.append({
                        'isin': isin,
                        'group': dh.isin_to_group[isin],
                        'industry': dh.isin_to_industry[isin],
                        'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0] if isin in sh_trend['isin'].values else False,
                        'beats_bench': bench_returns[isin] > bench_median
                    })
            
            if not stocks_with_info: 
                tranche_qtys[current_q_idx] = {}
                continue
                
            df_info = pd.DataFrame(stocks_with_info)
            
            # 4. Group Breadth Selection (Top 35%)
            group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
            top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
            
            # 5. Industry Breadth Selection (Top 35% within Top Groups)
            relevant_df = df_info[df_info['group'].isin(top_groups)]
            if relevant_df.empty: 
                tranche_qtys[current_q_idx] = {}
                continue
                
            industry_stats = relevant_df.groupby('industry').agg({
                'decreased': 'mean',
                'beats_bench': 'mean' # This is RSNP
            }).sort_values('decreased', ascending=False)
            
            top_industries_breadth = industry_stats.head(int(len(industry_stats) * 0.35))
            
            # 6. RSNP Filter: Bottom 50% of the breadth-selected industries
            if top_industries_breadth.empty:
                tranche_qtys[current_q_idx] = {}
                continue
                
            contrarian_industries = top_industries_breadth.sort_values('beats_bench').head(int(len(top_industries_breadth) * 0.50)).index.tolist()
            
            if not contrarian_industries:
                tranche_qtys[current_q_idx] = {}
                continue

            # 7. Selection & Weighting
            selected_weights = {}
            weight_per_industry = 1.0 / len(contrarian_industries)
            
            for ind in contrarian_industries:
                ind_stocks = relevant_df[relevant_df['industry'] == ind]['isin'].tolist()
                # Sort by Market Cap
                ind_univ = univ[univ['isin'].isin(ind_stocks)].sort_values('mc', ascending=False)
                top_3 = ind_univ.head(3)['isin'].tolist()
                
                if top_3:
                    weight_per_stock = weight_per_industry / len(top_3)
                    for isin in top_3:
                        selected_weights[isin] = weight_per_stock
            
            # Rebalance
            if current_q_idx <= 8:
                invest_val = q_allot
                tranche_map = {}
                for isin, weight in selected_weights.items():
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
                new_map = {}
                for isin, weight in selected_weights.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((investable * weight) / (p * 1.0065))
                        if qty > 0:
                            fees = fee_model.calculate_costs(p * qty, is_buy=True)
                            portfolio.buy(isin, date, p, qty, fees)
                            new_map[isin] = qty
                tranche_qtys[current_q_idx] = new_map
                
    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def run_contrarian_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    print("Running Contrarian RSNP Simulation (35/35/Bottom50)...")
    nav_contrarian = run_contrarian_rsnp_simulation(dh)
    
    print(f"Final NAV (Contrarian RSNP): {nav_contrarian.iloc[-1]:.2f}")
    
    years = [2020, 2021, 2022, 2023, 2024]
    for y in years:
        y_start = nav_contrarian[nav_contrarian.index.year < y]
        y_end = nav_contrarian[nav_contrarian.index.year == y]
        if not y_start.empty and not y_end.empty:
            ret = (y_end.iloc[-1] / y_start.iloc[-1]) - 1
            print(f"{y}: {ret*100:.2f}%")

    plt.figure(figsize=(10, 6))
    nav_contrarian.plot()
    plt.title("Contrarian RSNP: Top Breadth -> Bottom 50% RSNP (NAV)")
    plt.ylabel("Value (Base 100)")
    plt.grid(True)
    plt.savefig(repo_root / "contrarian_rsnp_nav.png")
    print(f"\nPlot saved to: contrarian_rsnp_nav.png")

if __name__ == "__main__":
    run_contrarian_study()
