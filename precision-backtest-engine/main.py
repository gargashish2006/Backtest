import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine

from strategies.industry_momentum import IndustryMomentumStrategy
from strategies.momentum import MomentumStrategy
from strategies.industry_shareholding import IndustryShareholdingStrategy
from utils.analytics import calculate_metrics

def run_backtest():
    # 1. Setup Data
    data_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/database")
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    
    # Load Benchmarks
    bench_dir = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine/benchmarks")
    dh.load_benchmarks(bench_dir)
    
    # 2. Setup Strategy
    strategy = IndustryShareholdingStrategy(dh)
    
    # 3. Setup Portfolio/Engine
    portfolio = Portfolio(initial_cash=10000000) # 1 Cr
    fee_model = FeeModel(transaction_fee_rate=0.0007, impact_cost_rate=0.001) # 0.07% fee, 0.1% impact
    tax_man = TaxManager()
    # Step 6: Cash yields 5% with 30% tax on gains
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 4. Define Rebalance Dates (Quarterly: 15th of Feb, May, Aug, Nov)
    rebalance_dates = []
    for year in range(2017, 2027): # Include 2026
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find closest trading date
            all_dates = dh.get_all_dates()
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                rebalance_dates.append(max(valid))
            
    # 5. Run Simulation
    engine.run(
        start_date="2017-05-15", 
        end_date="2026-02-05", 
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 6. Performance Reporting
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*50)
    print("INDUSTRY MOMENTUM RSNP PERFORMANCE REPORT (2017-2025)")
    print("="*50)
    for k, v in stats.items():
        print(f"{k:<20}: {v}")
    
    # 7. Analyze Top Winners
    trades = pd.DataFrame(portfolio.trade_log)
    if not trades.empty:
        # Group by ISIN to get total realized gain per stock
        stock_perf = trades.groupby('isin')['realized_gain'].sum().reset_index()
        stock_perf['name'] = stock_perf['isin'].map(dh.isin_to_name)
        top_winners = stock_perf.sort_values('realized_gain', ascending=False).head(10)
        
        print("\n" + "="*50)
        print("TOP 10 WINNING TRADES (BY REALIZED GAIN)")
        print("="*50)
        for _, row in top_winners.iterrows():
            print(f"{row['name']:<30}: ₹{row['realized_gain']:,.0f}")
        print("="*50)
    
    print("-" * 50)
    print(f"{'Total Taxes Paid':<20}: ₹{sum(t['total_tax'] for t in tax_man.tax_paid_history):,.0f}")
    print(f"{'Total Costs (Fee/Imp)':<20}: ₹{fee_model.total_fees:,.0f}")
    print(f"{'Final NAV':<20}: ₹{portfolio.nav_history[-1]['nav']:,.0f}")
    print("="*50)
    
    # Save Results
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    nav_df.to_csv(output_dir / "contrarian_shareholding_rsnp_nav.csv", index=False)

if __name__ == "__main__":
    run_backtest()
