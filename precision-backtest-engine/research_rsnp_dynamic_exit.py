import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def get_rsnp_quadrants(dh, date, df_info, univ):
    """
    Returns the RSNP rankings for industries within the breadth-selected set.
    """
    # 1. 35% Group / 35% Industry Breadth Filter (Standard)
    group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
    top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
    
    rel_df = df_info[df_info['group'].isin(top_groups)]
    if rel_df.empty: return pd.Series(), rel_df
    
    ind_stats = rel_df.groupby('industry').agg({'decreased': 'mean', 'beats_bench': 'mean'}).sort_values('decreased', ascending=False)
    top_ind_b = ind_stats.head(int(len(ind_stats) * 0.35))
    
    if top_ind_b.empty: return pd.Series(), rel_df
    
    return top_ind_b['beats_bench'].sort_values(), rel_df

def run_dynamic_exit_simulation(dh, scale_factor=10000.0):
    initial_total_capital = 100.0 
    initial_cash = initial_total_capital * scale_factor
    q_allot = 12.5 * scale_factor
    
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
    
    # Track holdings by (tranche_idx, industry)
    # structure: {tranche_idx: {industry_name: {isin: qty, isin: qty}}}
    tranches = {}
    current_q_idx = 0
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            
            # Preparation for selection and exit logic
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            univ = dh.get_universe(date, size=1000)
            univ_isins = set(univ['isin'].tolist())
            
            q_ago_date = max([d for d in all_dates if d <= date - pd.Timedelta(days=90)])
            prev_p = dh.get_daily_prices(q_ago_date)
            common = set(prices.keys()) & set(prev_p.keys()) & univ_isins
            rets = {isin: (prices[isin]/prev_p[isin]) - 1 for isin in common}
            bench_median = pd.Series(list(rets.values())).median()
            
            stocks_info = []
            for isin in common:
                if isin in dh.isin_to_group and isin in dh.isin_to_industry:
                    stocks_info.append({
                        'isin': isin,
                        'group': dh.isin_to_group[isin],
                        'industry': dh.isin_to_industry[isin],
                        'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0] if isin in sh_trend['isin'].values else False,
                        'beats_bench': rets[isin] > bench_median
                    })
            
            if not stocks_info: 
                # Still need to handle exits for existing tranches
                industry_rsnp_ranks = pd.Series()
                rel_df = pd.DataFrame()
            else:
                df_info = pd.DataFrame(stocks_info)
                industry_rsnp_ranks, rel_df = get_rsnp_quadrants(dh, date, df_info, univ)

            # --- DYNAMIC EXIT LOGIC ---
            # Check all active tranches (up to 8 previous)
            # If an industry is in the top 25% of RSNP (Q4), BOOK it.
            if not industry_rsnp_ranks.empty:
                n_inds = len(industry_rsnp_ranks)
                q4_threshold = industry_rsnp_ranks.iloc[int(n_inds * 0.75)] if n_inds > 4 else 999
                
                # Check active tranches
                for t_idx in range(max(1, current_q_idx - 7), current_q_idx):
                    if t_idx in tranches:
                        industries_to_sell = []
                        for ind_name in tranches[t_idx].keys():
                            # Does this industry exist in current RSNP map?
                            if ind_name in industry_rsnp_ranks.index:
                                rsnp_val = industry_rsnp_ranks.loc[ind_name]
                                if rsnp_val >= q4_threshold:
                                    industries_to_sell.append(ind_name)
                        
                        # Execute Sell
                        for ind_name in industries_to_sell:
                            # print(f"[{date}] Early Exit: Tranche {t_idx} Industry {ind_name} reached Q4.")
                            stock_map = tranches[t_idx].pop(ind_name)
                            for isin, qty in stock_map.items():
                                if isin in portfolio.holdings:
                                    p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                                    fees = fee_model.calculate_costs(p * qty, is_buy=False)
                                    res = portfolio.sell(isin, date, p, qty, fees)
                                    tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                                    portfolio.cash -= tax

            # --- NORMAL REBALANCE / ENTRY LOGIC ---
            # Handle standard 2-year cycle exit
            old_q = current_q_idx - 8
            if old_q in tranches:
                # Sell everything remaining in this old tranche
                for ind_name, stock_map in tranches[old_q].items():
                    for isin, qty in stock_map.items():
                        if isin in portfolio.holdings:
                            p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                            fees = fee_model.calculate_costs(p * qty, is_buy=False)
                            res = portfolio.sell(isin, date, p, qty, fees)
                            tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                            portfolio.cash -= tax
                del tranches[old_q]

            # Entry Logic: Q1 RSNP ONLY (0-25%)
            if not industry_rsnp_ranks.empty:
                n_inds = len(industry_rsnp_ranks)
                q1_threshold_val = industry_rsnp_ranks.iloc[int(n_inds * 0.25)] if n_inds > 4 else -1
                q1_inds = industry_rsnp_ranks[industry_rsnp_ranks <= q1_threshold_val].index.tolist()
                
                if q1_inds:
                    weights = {}
                    w_per_ind = 1.0 / len(q1_inds)
                    new_tranche_data = {}
                    
                    # Calculate investable
                    if current_q_idx <= 8:
                        invest_val = q_allot
                    else:
                        invest_val = portfolio.cash * 0.98
                    
                    for ind in q1_inds:
                        istocks = rel_df[rel_df['industry'] == ind]['isin'].tolist()
                        iuniv = univ[univ['isin'].isin(istocks)].sort_values('mc', ascending=False)
                        top3 = iuniv.head(3)['isin'].tolist()
                        if top3:
                            w_per_stock = (invest_val * w_per_ind) / len(top3)
                            ind_stock_map = {}
                            for isin in top3:
                                p = prices.get(isin)
                                if p:
                                    qty = int(w_per_stock / (p * 1.0065))
                                    if qty > 0:
                                        fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                        portfolio.buy(isin, date, p, qty, fees)
                                        ind_stock_map[isin] = qty
                            if ind_stock_map:
                                new_tranche_data[ind] = ind_stock_map
                    
                    tranches[current_q_idx] = new_tranche_data

    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def run_dynamic_exit_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    print("Running Dynamic Exit Simulation (Q1 Entry -> Q4 Early Exit)...")
    nav_dynamic = run_dynamic_exit_simulation(dh)
    
    print(f"Final NAV (Dynamic Exit): {nav_dynamic.iloc[-1]:.2f}")
    
    for y in [2020, 2021, 2022, 2023, 2024]:
        ystart = nav_dynamic[nav_dynamic.index.year < y]
        yend = nav_dynamic[nav_dynamic.index.year == y]
        if not ystart.empty and not yend.empty:
            ret = (yend.iloc[-1] / ystart.iloc[-1]) - 1
            print(f"  {y}: {ret*100:.2f}%")

    plt.figure(figsize=(10, 6))
    nav_dynamic.plot()
    plt.title("Dynamic Exit Rule: Q1 Entry -> Q4 RSNP Exit (Cash)")
    plt.ylabel("NAV (Base 100)")
    plt.grid(True)
    plt.savefig(repo_root / "dynamic_exit_nav.png")
    print(f"\nPlot saved to: dynamic_exit_nav.png")

if __name__ == "__main__":
    run_dynamic_exit_study()
