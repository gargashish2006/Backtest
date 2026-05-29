
import sys
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from utils.analytics import calculate_metrics

def run_cs15(rsnp_benchmark: str = 'top_1000'):
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-05-15"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            if d > pd.Timestamp(end_date):
                continue
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted(list(set([d for d in rdates if d >= pd.Timestamp(start_date)])))

    print(f"\nRSNP Benchmark: {rsnp_benchmark}")

    # 1. Setup Strategy
    strategy = CS15Strategy(dh, rsnp_benchmark=rsnp_benchmark)
    strategy.precompute_rsi(rdates)
    
    # 2. Setup Simulation (Rule 7 Costs/Taxes)
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005) # 0.15% fee, 0.5% impact
    tax_manager = TaxManager(0.20, 0.125) # 20% STCG, 12.5% LTCG
    
    # Rule 5: Cash yield 5%, cash tax 30%
    engine = SimEngine(dh, portfolio, fee_model, tax_manager, 
                        cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 3. Run
    print("Running CS15 Backtest to latest date...")
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)
    
    # 4. Results
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*40)
    print("CS15 STRATEGY PERFORMANCE")
    print("="*40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*40)
    
    # Save NAV for comparison later if needed
    suffix = f"_{rsnp_benchmark}"
    nav_df.to_csv(repo_root / f"cs15_nav{suffix}.csv", index=False)
    
    # Export current portfolio
    pos_list = []
    for isin, lots in portfolio.holdings.items():
        total_shares = sum(lot.remaining_qty for lot in lots)
        if total_shares > 0:
            avg_price = sum(lot.buy_price * lot.remaining_qty for lot in lots) / total_shares
            first_entry_date = min(lot.buy_date for lot in lots)
            pos_list.append({
                'isin': isin,
                'shares': total_shares,
                'entry_price': avg_price,
                'entry_date': first_entry_date
            })
    df_pos = pd.DataFrame(pos_list)
    stats_df = pd.read_parquet(repo_root / "database/stock_statistics.parquet")
    df_pos = pd.merge(df_pos, stats_df[['isin', 'company_name']], on='isin', how='left')
    
    latest_date_str = pd.Timestamp(end_date)
    # Get current prices for portfolio
    latest_avail = [d for d in all_dates if d <= latest_date_str]
    if latest_avail:
        last_dt = max(latest_avail)
        isins = list(portfolio.holdings.keys())
        p_df = dh.price_df[(dh.price_df['date'] == pd.Timestamp(last_dt)) & (dh.price_df['isin'].isin(isins))]
        prices = p_df.set_index('isin')['close']
        df_pos['current_price'] = df_pos['isin'].map(prices)
        df_pos['current_value'] = df_pos['shares'] * df_pos['current_price']
        total_nav = df_pos['current_value'].sum() + portfolio.cash
        df_pos['weight_pct'] = (df_pos['current_value'] / total_nav) * 100
        df_pos['profit_pct'] = (df_pos['current_price'] / df_pos['entry_price'] - 1) * 100
        cash_pct = (portfolio.cash / total_nav) * 100

        df_pos = df_pos.sort_values('weight_pct', ascending=False)
        print(f"\nPortfolio as of {last_dt.date()} (NAV={total_nav:,.0f}):")
        print(df_pos[['company_name', 'isin', 'weight_pct', 'profit_pct', 'entry_date']].to_string(index=False))
        print(f"{'Cash':>16}                          {cash_pct:.2f}")
        df_pos.to_csv(repo_root / f"cs15_portfolio_latest{suffix}.csv", index=False)
        print(f"\nPortfolio saved to cs15_portfolio_latest{suffix}.csv")

if __name__ == "__main__":
    benchmark = sys.argv[1] if len(sys.argv) > 1 else 'nifty_500'
    run_cs15(rsnp_benchmark=benchmark)
