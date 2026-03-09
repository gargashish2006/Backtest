import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_industry_basket_v2_simulation(dh, scale_factor=10000.0):
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
            
            # Logic for selection
            # 1. Sh Breadth (8Q)
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            if sh_trend.empty: continue
            
            # 2. Group Filter (Top 35%)
            stocks_with_info = []
            univ = dh.get_universe(date, size=1000)
            univ_isins = set(univ['isin'].tolist())
            
            for isin in sh_trend['isin'].tolist():
                if isin in univ_isins and isin in dh.isin_to_group and isin in dh.isin_to_industry:
                    stocks_with_info.append({
                        'isin': isin,
                        'group': dh.isin_to_group[isin],
                        'industry': dh.isin_to_industry[isin],
                        'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0]
                    })
            
            if not stocks_with_info: continue
            df_info = pd.DataFrame(stocks_with_info)
            
            # Group Breadth Calculation
            group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
            top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
            
            # 3. Top 5 Industries within Top Groups
            relevant_df = df_info[df_info['group'].isin(top_groups)]
            if relevant_df.empty: continue
            
            industry_stats = relevant_df.groupby('industry')['decreased'].mean().sort_values(ascending=False)
            top_5_industries = industry_stats.head(5).index.tolist()
            
            # 4. Select Max 3 Stocks per Industry (Higher MC first)
            selected_weights = {}
            for ind in top_5_industries:
                ind_stocks = relevant_df[relevant_df['industry'] == ind]['isin'].tolist()
                # Sort by Market Cap
                ind_univ = univ[univ['isin'].isin(ind_stocks)].sort_values('mc', ascending=False)
                top_3 = ind_univ.head(3)['isin'].tolist()
                
                if top_3:
                    weight_per_stock = 0.20 / len(top_3) # 20% split equally among 1-3 stocks
                    for isin in top_3:
                        selected_weights[isin] = weight_per_stock
            
            # Rebalance Logic
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

def run_industry_basket_v2_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    print("Running Industry Basket Simulation (5 Ind / 3 Stocks / 20% each)...")
    nav_basket = run_industry_basket_v2_simulation(dh)
    
    print(f"Final NAV (Hyper-Concentrated Industry Basket): {nav_basket.iloc[-1]:.2f}")
    
    years = [2020, 2021, 2022, 2023, 2024]
    for y in years:
        y_start = nav_basket[nav_basket.index.year < y]
        y_end = nav_basket[nav_basket.index.year == y]
        if not y_start.empty and not y_end.empty:
            ret = (y_end.iloc[-1] / y_start.iloc[-1]) - 1
            print(f"{y}: {ret*100:.2f}%")

    plt.figure(figsize=(10, 6))
    nav_basket.plot()
    plt.title("Hyper-Concentrated: Top 5 Ind (20% each) / 3 Stock (High MC)")
    plt.ylabel("NAV (Base 100)")
    plt.grid(True)
    plt.savefig(repo_root / "hyper_concentrated_industry_nav.png")
    print(f"\nPlot saved to: hyper_concentrated_industry_nav.png")

if __name__ == "__main__":
    run_industry_basket_v2_study()
