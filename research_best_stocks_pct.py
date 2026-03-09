import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def run_best_stock_analysis_pct():
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
    
    period_stats = []
    sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
    
    current_rebalance_idx = 0
    holdings_at_start = {}

    def get_period_data(date, portfolio):
        prices = dh.get_daily_prices(date)
        data = {}
        for isin, lots in portfolio.holdings.items():
            qty = sum(lot.remaining_qty for lot in lots)
            if qty > 0:
                data[isin] = {'qty': qty, 'price': prices.get(isin, 0)}
        return data

    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        engine._accrue_interest(date)
        portfolio.record_nav(date, prices)

        if date in rebalance_dates:
            if holdings_at_start or portfolio.trade_log:
                last_reb = rebalance_dates[current_rebalance_idx-1] if current_rebalance_idx > 0 else pd.Timestamp(start_date)
                trades = [t for t in portfolio.trade_log if last_reb < t['date'] <= date]
                all_isins = set(list(holdings_at_start.keys()) + [t['isin'] for t in trades])
                period_results = []
                for isin in all_isins:
                    start_val = holdings_at_start.get(isin, {}).get('qty', 0) * holdings_at_start.get(isin, {}).get('price', 0)
                    buys = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'BUY')
                    sells = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'SELL')
                    current_qty = sum(lot.remaining_qty for lot in portfolio.holdings.get(isin, []))
                    end_val = current_qty * prices.get(isin, 0)
                    
                    pnl = sells + end_val - start_val - buys
                    denominator = start_val + buys
                    ret_pct = pnl / denominator if denominator > 0 else 0
                    
                    period_results.append({
                        'isin': isin,
                        'pnl': pnl,
                        'ret_pct': ret_pct,
                        'start_date': last_reb,
                        'end_date': date
                    })
                
                if period_results:
                    # Find best % return
                    best_pct = max(period_results, key=lambda x: x['ret_pct'])
                    period_stats.append(best_pct)

            target_portfolio = strategy.calculate_selection(date)
            engine._execute_rebalance(date, target_portfolio, prices)
            holdings_at_start = get_period_data(date, portfolio)
            current_rebalance_idx += 1
        else:
            if hasattr(strategy, 'check_exits'):
                current_holdings = list(portfolio.holdings.keys())
                if current_holdings:
                    exits = strategy.check_exits(date, current_holdings)
                    if exits:
                        for isin in exits:
                            engine._sell_all(isin, date, prices)

    # Final Period
    last_reb = rebalance_dates[-1]
    trades = [t for t in portfolio.trade_log if last_reb < t['date'] <= pd.Timestamp(end_date)]
    prices = dh.get_daily_prices(pd.Timestamp(end_date))
    all_isins = set(list(holdings_at_start.keys()) + [t['isin'] for t in trades])
    period_results = []
    for isin in all_isins:
        start_val = holdings_at_start.get(isin, {}).get('qty', 0) * holdings_at_start.get(isin, {}).get('price', 0)
        buys = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'BUY')
        sells = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'SELL')
        current_qty = sum(lot.remaining_qty for lot in portfolio.holdings.get(isin, []))
        end_val = current_qty * (prices.get(isin, 0) if prices else 0)
        pnl = sells + end_val - start_val - buys
        denominator = start_val + buys
        ret_pct = pnl / denominator if denominator > 0 else 0
        period_results.append({
            'isin': isin,
            'pnl': pnl,
            'ret_pct': ret_pct,
            'start_date': last_reb,
            'end_date': pd.Timestamp(end_date)
        })
    if period_results:
        best_pct = max(period_results, key=lambda x: x['ret_pct'])
        period_stats.append(best_pct)

    # Analyze Overall Best
    trade_df = pd.DataFrame(portfolio.trade_log)
    stock_gains = trade_df.groupby('isin')['realized_gain'].sum().reset_index()
    final_prices = dh.get_daily_prices(max(dh.get_all_dates()))
    for isin, lots in portfolio.holdings.items():
        qty = sum(lot.remaining_qty for lot in lots)
        if qty > 0:
            p = final_prices.get(isin, 0)
            cost = sum(lot.buy_price * lot.remaining_qty for lot in lots)
            unrealized = (p * qty) - cost
            if isin in stock_gains['isin'].values:
                stock_gains.loc[stock_gains['isin'] == isin, 'realized_gain'] += unrealized
            else:
                new_row = pd.DataFrame({'isin': [isin], 'realized_gain': [unrealized]})
                stock_gains = pd.concat([stock_gains, new_row], ignore_index=True)

    best_stocks_overall = stock_gains.sort_values(by='realized_gain', ascending=False).head(10)

    print("\n" + "="*80)
    print("TOP 10 BEST CONTRIBUTING STOCKS (OVERALL)")
    print("="*80)
    for _, row in best_stocks_overall.iterrows():
        name = dh.isin_to_name.get(row['isin'], "Unknown")
        print(f"ISIN: {row['isin']:<12} | Name: {name:<30} | Net P&L: ₹{row['realized_gain']:,.0f}")

    print("\n" + "="*120)
    print("BEST PERCENTAGE GAIN PER REBALANCE PERIOD (15 Stocks)")
    print("="*120)
    print(f"{'Period Start':<12} | {'ISIN':<12} | {'Name':<40} | {'Gain %':>10} | {'Period P&L':>15}")
    print("-" * 120)
    for stat in period_stats:
        name = dh.isin_to_name.get(stat['isin'], "Unknown")
        print(f"{stat['start_date'].strftime('%Y-%m-%d'):<12} | {stat['isin']:<12} | {name:<40} | {stat['ret_pct']:>10.2%} | ₹{stat['pnl']:,.0f}")

    print("\n" + "="*120)
    print("TOP 5 LARGEST SINGLE-PERIOD PERCENTAGE GAINS")
    print("="*120)
    top_5_pct = sorted(period_stats, key=lambda x: x['ret_pct'], reverse=True)[:5]
    for stat in top_5_pct:
        name = dh.isin_to_name.get(stat['isin'], "Unknown")
        print(f"Gain: {stat['ret_pct']:>7.2%} | Date: {stat['start_date'].strftime('%Y-%m-%d')} | Name: {name:<40} | ISIN: {stat['isin']}")

if __name__ == "__main__":
    run_best_stock_analysis_pct()
