import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def run_worst_stock_analysis_pct():
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
    
    # We need to capture state at each rebalance
    period_stats = []
    
    sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
    
    current_rebalance_idx = 0
    next_rebalance = rebalance_dates[current_rebalance_idx] if rebalance_dates else None
    
    # Track holdings at start of period
    holdings_at_start = {} # isin -> qty, price
    
    def get_period_data(date, portfolio):
        # Capture current holdings
        prices = dh.get_daily_prices(date)
        data = {}
        for isin, lots in portfolio.holdings.items():
            qty = sum(lot.remaining_qty for lot in lots)
            if qty > 0:
                data[isin] = {'qty': qty, 'price': prices.get(isin, 0)}
        return data

    # Run simulation with period tracking
    for date in sim_dates:
        prices = dh.get_daily_prices(date)
        if not prices: continue
        engine._accrue_interest(date)
        portfolio.record_nav(date, prices)

        if date in rebalance_dates:
            # 1. Close out previous period stats
            if holdings_at_start or portfolio.trade_log:
                # Find trades since last rebalance
                last_reb = rebalance_dates[current_rebalance_idx-1] if current_rebalance_idx > 0 else pd.Timestamp(start_date)
                trades = [t for t in portfolio.trade_log if last_reb < t['date'] <= date]
                
                # Calculate P&L and % for each stock held/traded in period
                all_isins = set(list(holdings_at_start.keys()) + [t['isin'] for t in trades])
                period_results = []
                for isin in all_isins:
                    start_val = holdings_at_start.get(isin, {}).get('qty', 0) * holdings_at_start.get(isin, {}).get('price', 0)
                    buys = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'BUY')
                    sells = sum(t['net_value'] for t in trades if t['isin'] == isin and t['type'] == 'SELL')
                    
                    # Current value at end of period
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
                    # Find worst % return
                    worst_pct = min(period_results, key=lambda x: x['ret_pct'])
                    period_stats.append(worst_pct)

            # 2. Rebalance
            target_portfolio = strategy.calculate_selection(date)
            engine._execute_rebalance(date, target_portfolio, prices)
            
            # 3. Start new period
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

    # Final Period (from last rebalance to end)
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
        worst_pct = min(period_results, key=lambda x: x['ret_pct'])
        period_stats.append(worst_pct)

    print("\n" + "="*120)
    print("WORST PERCENTAGE LOSS PER REBALANCE PERIOD (15 Stocks)")
    print("="*120)
    print(f"{'Period Start':<12} | {'ISIN':<12} | {'Name':<35} | {'Loss %':>10} | {'Period P&L':>15}")
    print("-" * 120)
    
    overall_worst_pcts = []
    
    for stat in period_stats:
        name = dh.isin_to_name.get(stat['isin'], "Unknown")
        print(f"{stat['start_date'].strftime('%Y-%m-%d'):<12} | {stat['isin']:<12} | {name:<35} | {stat['ret_pct']:>10.2%} | -₹{abs(stat['pnl']):,.0f}")
        overall_worst_pcts.append(stat)

    print("\n" + "="*120)
    print("TOP 5 DEEPEST SINGLE-PERIOD PERCENTAGE LOSSES")
    print("="*120)
    top_5_pct = sorted(overall_worst_pcts, key=lambda x: x['ret_pct'])[:5]
    for stat in top_5_pct:
        name = dh.isin_to_name.get(stat['isin'], "Unknown")
        print(f"Loss: {stat['ret_pct']:>7.2%} | Date: {stat['start_date'].strftime('%Y-%m-%d')} | Name: {name:<35} | ISIN: {stat['isin']}")

if __name__ == "__main__":
    run_worst_stock_analysis_pct()
