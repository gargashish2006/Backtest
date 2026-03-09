import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager

def run_sh_change_basket_sim(dh, num_industries=5, max_per_industry=3, scale_factor=10000.0):
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
            
            # 1. Breadth Analysis on TOTAL universe
            sh_trend = dh.get_shareholder_trend(date, lookback_quarters=8)
            if sh_trend.empty: 
                selection_with_weights = {}
            else:
                stocks_info = []
                for _, row in sh_trend.iterrows():
                    isin = row['isin']
                    if isin in dh.isin_to_group and isin in dh.isin_to_industry:
                        stocks_info.append({
                            'isin': isin,
                            'group': dh.isin_to_group[isin],
                            'industry': dh.isin_to_industry[isin],
                            'decreased': row['decreased'],
                            'sh_change_pct': (row['curr_sh'] - row['prev_sh']) / row['prev_sh'] if row['prev_sh'] > 0 else 0
                        })
                
                if not stocks_info:
                    selection_with_weights = {}
                else:
                    df_info = pd.DataFrame(stocks_info)
                    
                    # Hierarchical Filtering (Breadth-based)
                    group_stats = df_info.groupby('group')['decreased'].mean()
                    top_groups = group_stats.sort_values(ascending=False).head(max(1, int(len(group_stats) * 0.35))).index.tolist()
                    
                    rel_df = df_info[df_info['group'].isin(top_groups)]
                    ind_stats = rel_df.groupby('industry')['decreased'].mean()
                    top_industries_breadth = ind_stats.sort_values(ascending=False).head(max(1, int(len(ind_stats) * 0.35))).index.tolist()
                    
                    # Qualified Pool (35/35 + Top 1000)
                    qualified_df = rel_df[rel_df['industry'].isin(top_industries_breadth)].copy()
                    univ = dh.get_universe(date, size=1000)
                    univ_isins = set(univ['isin'].tolist())
                    final_pool = qualified_df[qualified_df['isin'].isin(univ_isins)].copy()
                    
                    if final_pool.empty:
                        selection_with_weights = {}
                    else:
                        # --- BASKET FILLING LOGIC ---
                        # Rank by SH change % (Ascending = Max Decrease)
                        sorted_pool = final_pool.sort_values('sh_change_pct', ascending=True)
                        
                        selected_industries = []
                        industry_to_isins = {}
                        
                        for _, row in sorted_pool.iterrows():
                            ind = row['industry']
                            isin = row['isin']
                            
                            if ind not in selected_industries:
                                if len(selected_industries) < num_industries:
                                    selected_industries.append(ind)
                                    industry_to_isins[ind] = [isin]
                            else:
                                if len(industry_to_isins[ind]) < max_per_industry:
                                    industry_to_isins[ind].append(isin)
                            
                            # Optimized check: can we stop early?
                            # Only if we have N industries AND all have 3 stocks (if possible)
                            # But wait, some industries might not have 3 stocks in the pool.
                            # So we just iterate through the pool.
                        
                        # Weighting: Equal Industry Wise
                        # Each industry in selected_industries gets 1/len(selected_industries)
                        if not selected_industries:
                            selection_with_weights = {}
                        else:
                            total_n = len(selected_industries)
                            ind_weight = 1.0 / total_n
                            selection_with_weights = {}
                            for ind in selected_industries:
                                isins = industry_to_isins[ind]
                                stock_weight = ind_weight / len(isins)
                                for isin in isins:
                                    selection_with_weights[isin] = stock_weight

            # --- EXIT LOGIC ---
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
            
            # --- ENTRY LOGIC ---
            if selection_with_weights:
                new_tranche = {}
                invest_val = q_allot if current_q_idx <= 8 else portfolio.cash * 0.98
                
                for isin, weight in selection_with_weights.items():
                    p = prices.get(isin)
                    if p:
                        qty = int((invest_val * weight) / (p * 1.0065))
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
    output_dir = repo_root / "outputs"
    
    print("Running SH-Change Industry Basket Sensitivity Study (N=5 vs N=10)...")
    
    results = {}
    configs = [
        (5, 3, "5 Industries (Max 3 per Ind)"),
        (10, 3, "10 Industries (Max 3 per Ind)")
    ]
    
    for n, m, label in configs:
        print(f"  Testing {label}...")
        results[label] = run_sh_change_basket_sim(dh, num_industries=n, max_per_industry=m)
        print(f"    Final NAV: {results[label].iloc[-1]:.2f}")
    
    plt.figure(figsize=(12, 7))
    for label, nav in results.items():
        nav.plot(label=label)
    
    # Add Benchmark
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/my-backtesting-engine/analysis/outputs/benchmarks")
    dh.load_benchmarks(bench_dir)
    bench = dh.top_1000_bench[dh.top_1000_bench['date'] >= results["5 Industries (Max 3 per Ind)"].index[0]].copy()
    bench['nav'] = (bench['index_value'] / bench['index_value'].iloc[0]) * 100
    bench.set_index('date')['nav'].plot(label='Top 1000 Benchmark', color='black', alpha=0.5, linestyle='--')
    
    plt.title("SH-Change Industry Basket Sensitivity (Broad Universe)")
    plt.ylabel("NAV (Base 100)")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / "sh_change_basket_sensitivity.png")
    print(f"\nPlot saved to: outputs/sh_change_basket_sensitivity.png")

if __name__ == "__main__":
    run_study()
