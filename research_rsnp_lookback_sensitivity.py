import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def get_rsnp_ranks(dh, date, df_info, univ, lookback_days, all_dates):
    """
    Calculates RSNP rankings for industries with a custom lookback.
    """
    # Group/Industry Breadth Filter (Top 35/35)
    group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
    top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
    
    rel_df = df_info[df_info['group'].isin(top_groups)]
    if rel_df.empty: return pd.Series(), rel_df
    
    # Calculate RSNP with custom lookback
    lookback_date = max([d for d in all_dates if d <= date - pd.Timedelta(days=lookback_days)])
    curr_prices = dh.get_daily_prices(date)
    prev_prices = dh.get_daily_prices(lookback_date)
    
    univ_isins = set(univ['isin'].tolist())
    common = set(curr_prices.keys()) & set(prev_prices.keys()) & univ_isins
    
    if not common: return pd.Series(), rel_df
    
    rets = {isin: (curr_prices[isin]/prev_prices[isin]) - 1 for isin in common}
    bench_median = pd.Series(list(rets.values())).median()
    
    # Map back to rel_df
    rel_df = rel_df.copy()
    rel_df['beats_bench'] = rel_df['isin'].map(lambda x: rets.get(x, False) > bench_median if x in rets else False)
    
    ind_stats = rel_df.groupby('industry').agg({
        'decreased': 'mean',
        'beats_bench': 'mean' 
    }).sort_values('decreased', ascending=False)
    
    # QUALITY FLOOR: Must have > 0 cleaning breadth to qualify for the thematic pool
    ind_stats = ind_stats[ind_stats['decreased'] > 0]
    
    if ind_stats.empty: return pd.Series(), rel_df
    
    top_ind_b = ind_stats.head(max(1, int(len(ind_stats) * 0.35)))
    
    return top_ind_b['beats_bench'].sort_values(), rel_df

def run_simulation(dh, mode='static', rsnp_lookback=90, scale_factor=10000.0):
    initial_cash = 100.0 * scale_factor
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
    
    tranches = {}
    current_q_idx = 0
    
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        portfolio.record_nav(date, prices)
        
        if date in rebalance_dates:
            current_q_idx += 1
            
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            univ = dh.get_universe(date, size=1000)
            univ_isins = set(univ['isin'].tolist())
            
            # Breadth check for ranking
            stocks_info = []
            for isin in sh_trend['isin'].tolist():
                if isin in univ_isins and isin in dh.isin_to_group and isin in dh.isin_to_industry:
                    stocks_info.append({
                        'isin': isin,
                        'group': dh.isin_to_group[isin],
                        'industry': dh.isin_to_industry[isin],
                        'decreased': sh_trend[sh_trend['isin'] == isin]['decreased'].values[0]
                    })
            
            if not stocks_info:
                industry_rsnp_ranks = pd.Series()
                rel_df = pd.DataFrame()
            else:
                df_info = pd.DataFrame(stocks_info)
                industry_rsnp_ranks, rel_df = get_rsnp_ranks(dh, date, df_info, univ, rsnp_lookback, all_dates)

            # --- EXIT LOGIC ---
            if mode == 'dynamic' and not industry_rsnp_ranks.empty:
                n_inds = len(industry_rsnp_ranks)
                q4_thresh = industry_rsnp_ranks.iloc[int(n_inds * 0.75)] if n_inds > 4 else 999
                
                for t_idx in range(max(1, current_q_idx - 7), current_q_idx):
                    if t_idx in tranches:
                        to_sell = [ind for ind in tranches[t_idx] if ind in industry_rsnp_ranks.index and industry_rsnp_ranks[ind] >= q4_thresh]
                        for ind in to_sell:
                            smap = tranches[t_idx].pop(ind)
                            for isin, qty in smap.items():
                                if isin in portfolio.holdings:
                                    p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                                    fees = fee_model.calculate_costs(p * qty, is_buy=False)
                                    res = portfolio.sell(isin, date, p, qty, fees)
                                    tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                                    portfolio.cash -= tax

            # Standard 2-year cleanup
            old_q = current_q_idx - 8
            if old_q in tranches:
                for ind, smap in tranches[old_q].items():
                    for isin, qty in smap.items():
                        if isin in portfolio.holdings:
                            p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                            fees = fee_model.calculate_costs(p * qty, is_buy=False)
                            res = portfolio.sell(isin, date, p, qty, fees)
                            tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                            portfolio.cash -= tax
                del tranches[old_q]

            # --- ENTRY LOGIC (Q1 Only) ---
            if not industry_rsnp_ranks.empty:
                n = len(industry_rsnp_ranks)
                q1_thresh = industry_rsnp_ranks.iloc[int(n * 0.25)] if n > 4 else -1
                q1_inds = industry_rsnp_ranks[industry_rsnp_ranks <= q1_thresh].index.tolist()
                
                if q1_inds:
                    new_tranche = {}
                    invest_val = q_allot if current_q_idx <= 8 else portfolio.cash * 0.98
                    w_per_ind = 1.0 / len(q1_inds)
                    
                    for ind in q1_inds:
                        istks = rel_df[rel_df['industry'] == ind]['isin'].tolist()
                        iuniv = univ[univ['isin'].isin(istks)].sort_values('mc', ascending=False)
                        top3 = iuniv.head(3)['isin'].tolist()
                        if top3:
                            ind_map = {}
                            w_per_stk = (invest_val * w_per_ind) / len(top3)
                            for isin in top3:
                                p = prices.get(isin)
                                if p:
                                    qty = int(w_per_stk / (p * 1.0065))
                                    if qty > 0:
                                        fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                        portfolio.buy(isin, date, p, qty, fees)
                                        ind_map[isin] = qty
                            if ind_map: new_tranche[ind] = ind_map
                    tranches[current_q_idx] = new_tranche

    return pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor

def run_sensitivity_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    lookbacks = {90: '1Q', 365: '4Q', 730: '8Q'}
    modes = ['static', 'dynamic']
    
    all_results = {}
    
    for m in modes:
        for lb_days, lb_name in lookbacks.items():
            label = f"{m.capitalize()} {lb_name}"
            print(f"Running {label}...")
            nav = run_simulation(dh, mode=m, rsnp_lookback=lb_days)
            all_results[label] = nav
            print(f"  Final NAV: {nav.iloc[-1]:.2f}")
            
    # Summary Table
    print("\n" + "="*50)
    print(f"{'Configuration':<25} | {'Final NAV':<10} | {'2022 Ret':<10}")
    print("-" * 50)
    for label, nav in all_results.items():
        y22_start = nav[nav.index.year < 2022]
        y22_end = nav[nav.index.year == 2022]
        y22_ret = (y22_end.iloc[-1] / y22_start.iloc[-1]) - 1 if not y22_start.empty and not y22_end.empty else 0
        print(f"{label:<25} | {nav.iloc[-1]:<10.2f} | {y22_ret*100:<10.2F}%")
        
    plt.figure(figsize=(12, 8))
    for label, nav in all_results.items():
        nav.plot(label=label)
    plt.title("RSNP Lookback Sensitivity (1Q vs 4Q vs 8Q)")
    plt.ylabel("NAV (Base 100)")
    plt.legend()
    plt.grid(True)
    plt.savefig(repo_root / "rsnp_lookback_sensitivity.png")
    print(f"\nPlot saved to: rsnp_lookback_sensitivity.png")

if __name__ == "__main__":
    run_sensitivity_study()
