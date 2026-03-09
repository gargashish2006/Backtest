import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_quarterly_comparison():
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
    # Ensure end_date is included if it's a rebalance point, or add the final date for comparison
    final_date = max([d for d in all_dates if d <= pd.Timestamp(end_date)])
    check_dates = sorted(list(set(rebalance_dates + [final_date])))

    configs = [
        {
            "name": "RSI Entry",
            "rsi_exit": 0,
            "low_exit": False,
            "month_exit": False
        },
        {
            "name": "RSI Ent+Ext",
            "rsi_exit": 39,
            "low_exit": False,
            "month_exit": False
        }
    ]

    histories = {}

    for config in configs:
        strategy = ContrarianBreadthStrategy(
            data_handler=dh,
            num_stocks=15,
            rsnp_threshold=0.4,
            rsi_threshold=40,
            rsi_exit_threshold=config['rsi_exit'],
            weekly_low_exit=config['low_exit'],
            month_low_exit=config['month_exit']
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
        histories[config['name']] = nav_h['nav']

    # 2. Benchmark data
    bench_df = dh.top_1000_bench.copy()
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    bench_df = bench_df.set_index('date')

    # 3. Extract values at rebalance dates
    comparison_data = []
    for i in range(len(check_dates)):
        d = check_dates[i]
        row = {"Date": d.strftime("%Y-%m-%d")}
        for name, h in histories.items():
            row[name] = h.loc[d] if d in h.index else h.asof(d)
        row["Benchmark"] = bench_df.loc[d, 'index_value'] if d in bench_df.index else bench_df['index_value'].asof(d)
        comparison_data.append(row)

    df_comp = pd.DataFrame(comparison_data)
    
    # 4. Calculate Returns
    df_returns = df_comp.copy()
    for col in ["RSI Entry", "RSI Ent+Ext", "Benchmark"]:
        df_returns[f"{col} Ret"] = df_returns[col].pct_change()

    # 5. Output
    print("\n" + "="*110)
    print("REBALANCE-TO-REBALANCE PERFORMANCE COMPARISON")
    print("="*110)
    print(f"{'Date':<12} | {'RSI Entry':>15} | {'RSI Ent+Ext':>15} | {'Benchmark':>15}")
    print("-" * 110)
    
    for _, row in df_returns.iterrows():
        if pd.isna(row['RSI Entry Ret']):
            print(f"{row['Date']:<12} | {'INITIAL':>15} | {'INITIAL':>15} | {'INITIAL':>15}")
        else:
            print(f"{row['Date']:<12} | {row['RSI Entry Ret']:>14.2%} | {row['RSI Ent+Ext Ret']:>14.2%} | {row['Benchmark Ret']:>14.2%}")
    
    # Cumulative summary for the same period
    print("-" * 110)
    total_rsi = (df_comp["RSI Entry"].iloc[-1] / df_comp["RSI Entry"].iloc[0]) - 1
    total_exit = (df_comp["RSI Ent+Ext"].iloc[-1] / df_comp["RSI Ent+Ext"].iloc[0]) - 1
    total_bench = (df_comp["Benchmark"].iloc[-1] / df_comp["Benchmark"].iloc[0]) - 1
    print(f"{'TOTAL RETURN':<12} | {total_rsi:>14.2%} | {total_exit:>14.2%} | {total_bench:>14.2%}")
    print("="*110)

if __name__ == "__main__":
    run_quarterly_comparison()
