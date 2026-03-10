import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.accounting import TaxManager, FeeModel
from engine.portfolio import Portfolio

def run_structural_pilot():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # 1. Configuration
    start_date = pd.Timestamp("2019-05-15")
    all_dates = sorted(dh.get_all_dates())
    # Find exact entry date (nearest trading day >= 2019-05-15)
    entry_date = min([d for d in all_dates if d >= start_date])
    exit_date_target = entry_date + pd.DateOffset(years=3)
    exit_date = max([d for d in all_dates if d <= exit_date_target])
    
    signal_date = entry_date - pd.Timedelta(days=7)
    actual_signal_date = max([d for d in all_dates if d <= signal_date])
    
    lookback_q = 12 # 3 Years
    
    # 2. Accounting Setup
    initial_capital = 1000000.0 # 10 Lakhs
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_manager = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_capital)
    
    # 3. Selection Logic (Structural Alpha)
    print(f"Selecting Portfolio on {actual_signal_date.date()} using 12Q SH Lookback...")
    universe = dh.get_universe(actual_signal_date, size=1000)
    u_isins = set(universe['isin'].tolist())
    
    # Get 12Q SH signal
    curr_q, prev_q = "Mar-2019", "Mar-2016"
    sh_df = dh.shareholding_df
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'c_sh'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'p_sh'})
    
    merged = pd.merge(curr_sh, prev_sh, on='isin', how='inner')
    merged = merged[merged['isin'].isin(u_isins)]
    merged['sh_dec'] = merged['c_sh'] < merged['p_sh']
    merged['industry'] = merged['isin'].map(dh.isin_to_industry)
    
    ind_stats = merged.groupby('industry')['sh_dec'].mean().reset_index()
    top_industries = ind_stats.sort_values('sh_dec', ascending=False).head(5)['industry'].tolist()
    
    print(f"Top 5 Industries Selected: {top_industries}")
    
    selected_isins = []
    for ind in top_industries:
        ind_stocks = universe[universe['isin'].map(dh.isin_to_industry) == ind].sort_values('mc', ascending=False)
        selected_isins.extend(ind_stocks.head(3)['isin'].tolist())
        
    print(f"Selected {len(selected_isins)} stocks for the 3-year hold.")
    
    # 4. Execute Entry
    entry_prices = dh.get_daily_prices(entry_date)
    cash_per_stock = initial_capital / len(selected_isins)
    
    for isin in selected_isins:
        p = entry_prices.get(isin, 0)
        if p > 0:
            qty = int(cash_per_stock / (p * (1 + 0.0065)))
            fees = fee_model.calculate_costs(p * qty, is_buy=True)
            portfolio.buy(isin, entry_date, p, qty, fees)
            
    # 5. Track NAV daily
    active_dates = [d for d in all_dates if entry_date <= d <= exit_date]
    for d in active_dates:
        prices = dh.get_daily_prices(d)
        portfolio.record_nav(d, prices)
        
    # 6. Execute Exit (Tax Calculation)
    exit_prices = dh.get_daily_prices(exit_date)
    for isin in list(portfolio.holdings.keys()):
        p = exit_prices.get(isin, 0)
        if p > 0:
            qty = sum(lot.remaining_qty for lot in portfolio.holdings[isin])
            fees = fee_model.calculate_costs(p * qty, is_buy=False)
            res = portfolio.sell(isin, exit_date, p, qty, fees)
            tax_manager.process_realized_gains(exit_date, res['stcg_base'], res['ltcg_base'])
            
    # Deduct all taxes at end
    total_tax = sum(t['total_tax'] for t in tax_manager.tax_paid_history)
    portfolio.cash -= total_tax
    
    final_nav = portfolio.cash + portfolio.get_market_value(exit_prices)
    total_return = (final_nav / initial_capital) - 1
    
    # 7. Benchmark Comparison (Top 1000 Equal Weight)
    bench_isins = [isin for isin in list(u_isins) if isin in entry_prices and entry_prices[isin] > 0]
    
    # Equal weight proxy: average of returns
    prices_t = dh.price_df[dh.price_df['isin'].isin(bench_isins)]
    prices_t = prices_t[(prices_t['date'] >= entry_date) & (prices_t['date'] <= exit_date)]
    
    # Calculate daily average return for benchmark
    bench_pivot = prices_t.pivot(index='date', columns='isin', values='close')
    daily_bench_rets = bench_pivot.pct_change().mean(axis=1)
    bench_cum_nav = (1 + daily_bench_rets.fillna(0)).cumprod() * initial_capital
    
    # 8. Results Visualization
    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    df_nav['bench'] = bench_cum_nav
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'], label=f"Structural Strategy (LTCG Net)")
    plt.plot(df_nav['bench'], label="Top 1000 Benchmark (Gross)", alpha=0.7)
    plt.title(f"3-Year Structural Alpha Pilot: May 2019 - May 2022\nTotal Net Return: {total_return:.1%}")
    plt.ylabel("Portfolio Value (₹)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "structural_pilot_results.png")
    
    print("\nStructural Strategy (3Y Hold) Final Report:")
    print(f"Start Date: {entry_date.date()}")
    print(f"End Date:   {exit_date.date()}")
    print(f"Final NAV:  ₹{final_nav:,.2f}")
    print(f"Net Return: {total_return:.2%}")
    print(f"CAGR:       {((final_nav/initial_capital)**(1/3)-1):.2%}")
    print(f"Bench Net:  {((bench_cum_nav.iloc[-1]/initial_capital)-1):.2%}")

if __name__ == "__main__":
    run_structural_pilot()
