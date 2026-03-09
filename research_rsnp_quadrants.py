import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_rsnp_quadrant_simulations(dh, scale_factor=10000.0):
    quadrants = {
        'Q1 (0-25%)': (0.00, 0.25),
        'Q2 (25-50%)': (0.25, 0.50),
        'Q3 (50-75%)': (0.50, 0.75),
        'Q4 (75-100%)': (0.75, 1.00)
    }
    
    results = {}
    
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for y in range(2019, 2025):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in all_dates if d >= dt]
            if avail:
                rebalance_dates.append(avail[0])
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    start_date = rebalance_dates[0]
    sim_dates = [d for d in all_dates if start_date <= d <= all_dates[-1]]

    for q_name, (low_p, high_p) in quadrants.items():
        print(f"Running Simulation for {q_name}...")
        
        initial_total_capital = 100.0 
        initial_cash = initial_total_capital * scale_factor
        q_allot = 12.5 * scale_factor
        
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        portfolio = Portfolio(initial_cash=initial_cash)
        
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
                
                # 3. Benchmark Proxy (Top 1000 median)
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
                    tranche_qtys[current_q_idx] = {}
                    continue
                
                df_info = pd.DataFrame(stocks_info)
                
                # 4. Group Top 35%
                group_stats = df_info.groupby('group')['decreased'].mean().sort_values(ascending=False)
                top_groups = group_stats.head(int(len(group_stats) * 0.35)).index.tolist()
                
                # 5. Industry Top 35%
                rel_df = df_info[df_info['group'].isin(top_groups)]
                if rel_df.empty:
                    tranche_qtys[current_q_idx] = {}
                    continue
                
                ind_stats = rel_df.groupby('industry').agg({'decreased': 'mean', 'beats_bench': 'mean'}).sort_values('decreased', ascending=False)
                top_ind_b = ind_stats.head(int(len(ind_stats) * 0.35))
                
                if top_ind_b.empty:
                    tranche_qtys[current_q_idx] = {}
                    continue
                
                # 6. Quadrant Filter (RSNP)
                sorted_rsnp = top_ind_b.sort_values('beats_bench')
                n = len(sorted_rsnp)
                start_idx = int(n * low_p)
                end_idx = int(n * high_p) if high_p < 1.0 else n
                
                q_industries = sorted_rsnp.iloc[start_idx:end_idx].index.tolist()
                
                if not q_industries:
                    tranche_qtys[current_q_idx] = {}
                    continue

                # 7. Selection (Max 3 Stocks)
                weights = {}
                w_per_ind = 1.0 / len(q_industries)
                for ind in q_industries:
                    istocks = rel_df[rel_df['industry'] == ind]['isin'].tolist()
                    iuniv = univ[univ['isin'].isin(istocks)].sort_values('mc', ascending=False)
                    top3 = iuniv.head(3)['isin'].tolist()
                    if top3:
                        w_per_stock = w_per_ind / len(top3)
                        for isin in top3:
                            weights[isin] = w_per_stock
                
                # Rebalance
                if current_q_idx <= 8:
                    invest_val = q_allot
                    tmap = {}
                    for isin, w in weights.items():
                        p = prices.get(isin)
                        if p:
                            qty = int((invest_val * w) / (p * 1.0065))
                            if qty > 0:
                                fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                portfolio.buy(isin, date, p, qty, fees)
                                tmap[isin] = qty
                    tranche_qtys[current_q_idx] = tmap
                else:
                    old_q = current_q_idx - 8
                    old_m = tranche_qtys.get(old_q, {})
                    if old_m:
                        for isin, oqty in old_m.items():
                            if isin in portfolio.holdings:
                                p = prices.get(isin) or portfolio.last_prices.get(isin, 0)
                                fees = fee_model.calculate_costs(p * oqty, is_buy=False)
                                res = portfolio.sell(isin, date, p, oqty, fees)
                                tax = tax_man.process_realized_gains(date, res['stcg_base'], res['ltcg_base'])
                                portfolio.cash -= tax
                    
                    investable = portfolio.cash * 0.98
                    nmap = {}
                    if weights:
                        for isin, w in weights.items():
                            p = prices.get(isin)
                            if p:
                                qty = int((investable * w) / (p * 1.0065))
                                if qty > 0:
                                    fees = fee_model.calculate_costs(p * qty, is_buy=True)
                                    portfolio.buy(isin, date, p, qty, fees)
                                    nmap[isin] = qty
                    tranche_qtys[current_q_idx] = nmap
        
        results[q_name] = pd.DataFrame(portfolio.nav_history).set_index('date')['nav'] / scale_factor
        print(f"Final NAV for {q_name}: {results[q_name].iloc[-1]:.2f}")

    return results

def run_quadrant_study():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    res = run_rsnp_quadrant_simulations(dh)
    
    plt.figure(figsize=(12, 7))
    for name, nav in res.items():
        nav.plot(label=name)
        
        # Yearly returns
        print(f"\n{name} Annual Returns:")
        for y in [2020, 2021, 2022, 2023, 2024]:
            ystart = nav[nav.index.year < y]
            yend = nav[nav.index.year == y]
            if not ystart.empty and not yend.empty:
                ret = (yend.iloc[-1] / ystart.iloc[-1]) - 1
                print(f"  {y}: {ret*100:.2f}%")
                
    plt.title("RSNP Quadrant Sweep: Structural Alpha vs Price Performance (35/35/Q1-Q4)")
    plt.ylabel("NAV (Base 100)")
    plt.legend()
    plt.grid(True)
    plt.savefig(repo_root / "rsnp_quadrants_nav.png")
    print(f"\nPlot saved to: rsnp_quadrants_nav.png")

if __name__ == "__main__":
    run_quadrant_study()
