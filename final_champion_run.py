import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_final_champion():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy (Quarterly)
    # Default params are the champion params: 
    # num_stocks=15, max_per_ind=3, rsnp=0.40, lookback=4 (default)
    strategy = ContrarianBreadthStrategy(dh)
    
    # 2b. Pre-compute RSI cache (CRITICAL: without this, RSI entry/exit filters are disabled)
    # Must be called before run() to populate rsi_cache used by check_exits and calculate_selection
    all_dates_pre = dh.get_all_dates()
    pre_rebalance_dates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            valid = [dt for dt in all_dates_pre if dt <= d]
            if valid:
                reb = max(valid)
                if reb not in pre_rebalance_dates:
                    pre_rebalance_dates.append(reb)
    pre_rebalance_dates.sort()
    strategy.precompute_rsi(pre_rebalance_dates)
    
    # 3. Define Rebalance Dates (Quarterly)
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
    
    rebalance_dates.sort()
    
    # Start from May 2017 as established in the baseline
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    # Filter rebalance dates
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date)]
    
    print(f"Starting FINAL CHAMPION (Quarterly) Backtest...")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    
    # 4. Run Backtest
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
    
    # 5. Generate Report Data
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    # Save NAV history
    nav_df.to_csv(base_path / "outputs/final_champion_nav.csv", index=False)
    
    print("\n" + "="*60)
    print("FINAL CHAMPION STRATEGY PERFORMANCE")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*60)
    
    # Create Markdown Report
    report_path = base_path / "Final_Quarterly_Champion_Report.md"
    with open(report_path, "w") as f:
        f.write("# Final Quarterly Champion Strategy Report\n\n")
        f.write("## Strategy Configuration\n")
        f.write("- **Universe**: Top 1000 Market Cap (Dynamic)\n")
        f.write("- **Rebalance Frequency**: Quarterly (Feb, May, Aug, Nov)\n")
        f.write("- **Selection Criteria**:\n")
        f.write("  1. Liquidity > 0.005% of Market Cap\n")
        f.write("  2. Industry Group Shareholder Decrease (Top 40%)\n")
        f.write("  3. Industry Shareholder Decrease (> 50%)\n")
        f.write("  4. RSNP Breadth Filter (> 0.40)\n")
        f.write("- **Portfolio Construction**: Max 15 Stocks, Max 3 per Industry, Equal Weight\n\n")
        
        f.write("## Performance Metrics (May 2017 - Feb 2026)\n")
        f.write("| Metric | Value |\n")
        f.write("|---|---|\n")
        for k, v in stats.items():
            f.write(f"| {k} | {v} |\n")
            
    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    run_final_champion()
