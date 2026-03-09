import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def calculate_periodic_performance():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy
    strategy = ContrarianBreadthStrategy(dh)
    
    # 3. Define Rebalance Dates
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find the actual trading day on or before this date
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    # Filter for simulation period
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp("2017-05-15") and d <= pd.Timestamp("2026-02-05")]
    rebalance_dates.sort()
    
    # 4. Run Simulation while capturing NAV at rebalance points
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date="2017-05-15",
        end_date="2026-02-05",
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 5. Extract Periodic Data
    nav_history = pd.DataFrame(portfolio.nav_history)
    bench_history = dh.top_1000_bench[['date', 'index_value']]
    
    periodic_results = []
    
    # We want returns from rebalance i to rebalance i+1
    for i in range(len(rebalance_dates)):
        start_date = rebalance_dates[i]
        
        # Determine end of period (next rebalance or end of sim)
        if i + 1 < len(rebalance_dates):
            end_date = rebalance_dates[i+1]
        else:
            end_date = pd.Timestamp("2026-02-05")
            
        # Get Strategy NAV at start and end
        # We need the NAV exactly at the close of those days
        nav_start = nav_history[nav_history['date'] == start_date]['nav'].iloc[0]
        nav_end = nav_history[nav_history['date'] == end_date]['nav'].iloc[0]
        
        # Get Benchmark at start and end
        bench_start = bench_history[bench_history['date'] <= start_date]['index_value'].iloc[-1]
        bench_end = bench_history[bench_history['date'] <= end_date]['index_value'].iloc[-1]
        
        strat_return = (nav_end / nav_start) - 1
        bench_return = (bench_end / bench_start) - 1
        alpha = strat_return - bench_return
        
        periodic_results.append({
            'Period Start': start_date.strftime('%Y-%m-%d'),
            'Period End': end_date.strftime('%Y-%m-%d'),
            'Strategy Return': f"{strat_return:.2%}",
            'Benchmark Return': f"{bench_return:.2%}",
            'Alpha': f"{alpha:.2%}"
        })
        
    df = pd.DataFrame(periodic_results)
    print("\nREBALANCE-TO-REBALANCE PERFORMANCE")
    print(df.to_string(index=False))

if __name__ == "__main__":
    calculate_periodic_performance()
