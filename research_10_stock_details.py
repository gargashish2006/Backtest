import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_detailed_10stock_returns():
    # 1. Setup
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(str(repo_root / "database" / "price_data.parquet"))
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Rebalance Dates (Quarterly)
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
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
    final_date = max([d for d in all_dates if d <= pd.Timestamp(end_date)])
    check_dates = sorted(list(set(rebalance_dates + [final_date])))

    # Run for 10 stocks only
    strategy = ContrarianBreadthStrategy(
        data_handler=dh,
        num_stocks=10,
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
    
    nav_h = pd.DataFrame(portfolio.nav_history).set_index('date')
    bench_df = dh.top_1000_bench.copy()
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    bench_df = bench_df.set_index('date')

    comparison_data = []
    for i in range(len(check_dates)):
        d = check_dates[i]
        row = {"Date": d.strftime("%Y-%m-%d")}
        row["Strategy"] = nav_h.loc[d, 'nav'] if d in nav_h.index else nav_h['nav'].asof(d)
        row["Benchmark"] = bench_df.loc[d, 'index_value'] if d in bench_df.index else bench_df['index_value'].asof(d)
        comparison_data.append(row)

    df_comp = pd.DataFrame(comparison_data)
    df_comp["Strategy Ret"] = df_comp["Strategy"].pct_change()
    df_comp["Benchmark Ret"] = df_comp["Benchmark"].pct_change()

    print("\n| Period | Strategy (10 Stocks) | Benchmark | Alpha |")
    print("| :--- | :---: | :---: | :---: |")
    
    for i in range(1, len(df_comp)):
        row = df_comp.iloc[i]
        prev_row = df_comp.iloc[i-1]
        period = f"{prev_row['Date'][:7]} to {row['Date'][:7]}"
        s_ret = row['Strategy Ret']
        b_ret = row['Benchmark Ret']
        alpha = s_ret - b_ret
        bold = "**" if s_ret > b_ret else ""
        print(f"| {period} | {bold}{s_ret:.2%}{bold} | {b_ret:.2%} | {alpha:.2%} |")

if __name__ == "__main__":
    run_detailed_10stock_returns()
