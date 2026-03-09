import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine

from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_contrarian_breadth_backtest():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = base_path / "benchmarks"
    dh.load_benchmarks(bench_dir)
    
    # 2. Setup Strategy
    strategy = ContrarianBreadthStrategy(dh, max_per_industry=3)
    
    # 3. Setup Portfolio/Engine
    portfolio = Portfolio(initial_cash=10000000) # 1 Cr
    # Transaction costs: 0.15% (Brokerage+STT) + 0.5% Impact (conservative)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005) 
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125) # Recent budget rates
    
    # Engine logic for cash interest (5% yield, 30% tax)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, 
                       cash_yield_rate=0.05, 
                       cash_tax_rate=0.30)
    
    # 4. Define Rebalance Dates (Quarterly: 15th of Feb, May, Aug, Nov)
    rebalance_dates = []
    all_trading_dates = dh.get_all_dates()
    for year in range(2017, 2027): # Running from 2017 to Feb 2026
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find closest trading day <= 15th
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid:
                rebalance_dates.append(max(valid))
    
    # 5. Run Simulation
    print("Starting Contrarian Breadth Backtest...")
    engine.run(
        start_date="2017-05-15", 
        end_date="2026-02-05", # Max data date
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 6. Reporting
    nav_df = pd.DataFrame(portfolio.nav_history)
    if not nav_df.empty:
        stats = calculate_metrics(nav_df)
        print("\n" + "="*50)
        print("CONTRARIAN BREADTH STRATEGY PERFORMANCE")
        print("="*50)
        for k, v in stats.items():
            print(f"{k:<20}: {v}")
        
        # Taxes & Costs
        total_tax = sum(t['total_tax'] for t in tax_man.tax_paid_history)
        print(f"{'Total Taxes Paid':<20}: ₹{total_tax:,.0f}")
        print(f"{'Total Execution Costs':<20}: ₹{fee_model.total_fees:,.0f}")
        print(f"{'Final NAV':<20}: ₹{portfolio.nav_history[-1]['nav']:,.0f}")
        print("="*50)
        
        # Save Outputs
        output_dir = base_path / "outputs"
        output_dir.mkdir(exist_ok=True)
        nav_df.to_csv(output_dir / "contrarian_breadth_benchmark_nav.csv", index=False)
        
        # Trade Log Summary
        trades = pd.DataFrame(portfolio.trade_log)
        if not trades.empty:
            trades.to_csv(output_dir / "contrarian_breadth_trades.csv", index=False)
            print(f"Results saved to outputs directory.")
    else:
        print("No NAV history generated. Check strategy signals.")

if __name__ == "__main__":
    run_contrarian_breadth_backtest()
