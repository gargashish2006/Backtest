import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def run_worst_stock_analysis():
    # 1. Setup
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-02-05"
    all_dates = dh.get_all_dates()

    # Rebalance Dates (Quarterly)
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date):
                    rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    # Run 15-stock Official Strategy
    strategy = ContrarianBreadthStrategy(
        data_handler=dh,
        num_stocks=15,
        rsnp_threshold=0.4,
        rsi_threshold=40,
        rsi_exit_threshold=39
    )
    
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates,
        verbose=False
    )

    # 2. Analyze Overall Worst Stocks
    trade_df = pd.DataFrame(portfolio.trade_log)
    
    # Calculate realized gains per stock
    stock_gains = trade_df.groupby('isin')['realized_gain'].sum().reset_index()
    
    # Add open position value as "unrealized" gain
    final_prices = dh.get_daily_prices(max(dh.get_all_dates()))
    for isin, lots in portfolio.holdings.items():
        qty = sum(lot.remaining_qty for lot in lots)
        if qty > 0:
            p = final_prices.get(isin, 0)
            cost = sum(lot.buy_price * lot.remaining_qty for lot in lots)
            unrealized = (p * qty) - cost
            # Update stock_gains or add a new entry
            if isin in stock_gains['isin'].values:
                stock_gains.loc[stock_gains['isin'] == isin, 'realized_gain'] += unrealized
            else:
                new_row = pd.DataFrame({'isin': [isin], 'realized_gain': [unrealized]})
                stock_gains = pd.concat([stock_gains, new_row], ignore_index=True)

    worst_stocks_overall = stock_gains.sort_values(by='realized_gain').head(10)

    print("\n" + "="*80)
    print("TOP 10 WORST CONTRIBUTING STOCKS (OVERALL)")
    print("="*80)
    for _, row in worst_stocks_overall.iterrows():
        name = dh.isin_to_name.get(row['isin'], "Unknown")
        print(f"ISIN: {row['isin']:<12} | Name: {name:<30} | Net P&L: -₹{abs(row['realized_gain']):,.0f}")

    # 3. Analyze Period-wise Worst Stocks
    # We define periods by the rebalance dates
    periods = []
    sorted_reb = sorted(rebalance_dates)
    for i in range(len(sorted_reb)-1):
        periods.append((sorted_reb[i], sorted_reb[i+1]))
    # Add final period
    periods.append((sorted_reb[-1], pd.Timestamp(end_date)))

    print("\n" + "="*110)
    print("WORST PERFORMING STOCK PER REBALANCE PERIOD")
    print("="*110)
    print(f"{'Period Start':<12} | {'ISIN':<12} | {'Name':<40} | {'Period P&L':>15}")
    print("-" * 110)

    for start, end in periods:
        period_trades = trade_df[(trade_df['date'] > start) & (trade_df['date'] <= end)]
        if period_trades.empty: continue
        
        # We also need to check "mark-to-market" for stocks held across the boundary
        # For simplicity, let's just use realized gains during the period
        period_gains = period_trades.groupby('isin')['realized_gain'].sum()
        if not period_gains.empty:
            worst_p_isin = period_gains.idxmin()
            worst_p_val = period_gains.min()
            if worst_p_val < 0:
                name = dh.isin_to_name.get(worst_p_isin, "Unknown")
                print(f"{start.strftime('%Y-%m-%d'):<12} | {worst_p_isin:<12} | {name:<40} | -₹{abs(worst_p_val):,.0f}")

if __name__ == "__main__":
    run_worst_stock_analysis()
