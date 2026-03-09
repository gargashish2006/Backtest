import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.structural_alpha_strategy import StructuralAlphaStrategy

def run_production_comparison():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # 1. Setup
    initial_cash = 1000000.0
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    portfolio = Portfolio(initial_cash=initial_cash)
    
    engine = SimEngine(dh, portfolio, fee_model, tax_man)
    
    # Actually, let's use a slightly broader portfolio for production: 30 stocks (Top 10 industries x 3 stocks)
    strategy = StructuralAlphaStrategy(dh, num_stocks=30, max_per_industry=3)
    
    # 3. Benchmark Loading
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 4. Dates
    rebalance_dates = []
    for y in range(2019, 2023):
        for m in [2, 5, 8, 11]:
            dt = pd.Timestamp(year=y, month=m, day=15)
            avail = [d for d in dh.get_all_dates() if d >= dt]
            if avail:
                rebalance_dates.append(avail[0])
    
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2019-05-15")]
    
    start_date = "2019-05-15"
    end_date = "2022-12-31"
    
    # 5. Run Simulation
    import matplotlib.pyplot as plt
    engine.run(start_date, end_date, strategy.calculate_selection, rebalance_dates)
    
    # 6. Benchmark Comparison
    bench = dh.top_1000_bench[(dh.top_1000_bench['date'] >= pd.to_datetime(start_date)) & 
                               (dh.top_1000_bench['date'] <= pd.to_datetime(end_date))].copy()
    bench['norm_nav'] = bench['index_value'] / bench['index_value'].iloc[0] * initial_cash
    
    df_nav = pd.DataFrame(portfolio.nav_history).set_index('date')
    
    # 7. Final Report & Plot
    final_prices = dh.get_daily_prices(df_nav.index[-1])
    final_nav = portfolio.cash + portfolio.get_market_value(final_prices)
    bench_final = bench['norm_nav'].iloc[-1]
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_nav['nav'], label=f"Structural Alpha Strategy (Net)", linewidth=2)
    plt.plot(bench['date'], bench['norm_nav'], label="Top 1000 Equal Weight Benchmark", alpha=0.7)
    plt.title(f"Structural Alpha vs Top 1000 Benchmark (May 2019 - Dec 2022)\nStrategy: {((final_nav/initial_cash)-1):.1%} | Bench: {((bench_final/initial_cash)-1):.1%}")
    plt.ylabel("Portfolio Value (₹)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(repo_root / "structural_alpha_vs_benchmark.png")
    
    print(f"\nPRODUCTION COMPARISON COMPLETE")
    print(f"Period: {start_date} to {end_date}")
    print(f"Strategy Final NAV: ₹{final_nav:,.2f} ({((final_nav/initial_cash)-1):.2%})")
    print(f"Benchmark Final NAV: ₹{bench_final:,.2f} ({((bench_final/initial_cash)-1):.2%})")
    print(f"Alpha: {((final_nav/bench_final)-1):.2%}")

if __name__ == "__main__":
    run_production_comparison()
