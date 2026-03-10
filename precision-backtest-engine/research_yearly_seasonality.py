import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def run_yearly_seasonality_comparison():
    # 1. Setup Data
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    data_path = base_path / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy
    strategy = ContrarianBreadthStrategy(dh)
    all_dates = dh.get_all_dates()
    
    months = {
        2: "February",
        5: "May",
        8: "August",
        11: "November"
    }
    
    results = []

    for m_num, m_name in months.items():
        print(f"\nRunning Yearly Rebalance: {m_name}...")
        
        # Define Yearly Rebalance Dates for this specific month
        rebalance_dates = []
        for year in range(2017, 2027):
            d = pd.Timestamp(year=year, month=m_num, day=15)
            # Find the actual trading day on or before mid-month
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb_dt = max(valid)
                if reb_dt not in rebalance_dates:
                    rebalance_dates.append(reb_dt)
        
        rebalance_dates.sort()
        start_date = rebalance_dates[0]
        end_date = "2026-02-05"
        
        # 3. Run Backtest
        portfolio = Portfolio(initial_cash=10000000)
        fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
        tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
        engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
        
        engine.run(
            start_date=start_date,
            end_date=end_date,
            strategy_func=strategy.calculate_selection,
            rebalance_dates=rebalance_dates
        )
        
        nav_df = pd.DataFrame(portfolio.nav_history)
        metrics = calculate_metrics(nav_df)
        metrics['Month'] = m_name
        results.append(metrics)

    # 4. Report
    summary_df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("YEARLY REBALANCE SEASONALITY COMPARISON")
    print("="*80)
    cols = ['Month', 'Absolute Return', 'CAGR', 'Max Drawdown', 'Sharpe Ratio']
    print(summary_df[cols].to_string(index=False))
    print("="*80)

if __name__ == "__main__":
    run_yearly_seasonality_comparison()
