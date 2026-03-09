
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

def generate_final_rebalance():
    # 1. Setup Data Paths
    repo_root = Path(__file__).parent
    data_path = repo_root / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 2. FINAL STRATEGY PARAMETERS (Champion Baseline)
    # These parameters match the 489% absolute return / 22.5% CAGR result.
    strategy = ContrarianBreadthStrategy(
        dh,
        num_stocks=15,
        max_per_industry=3,
        universe_size=1000,
        liquidity_threshold_pct=0.00005,
        industry_group_top_pct=0.50,
        industry_decrease_min_pct=0.50,
        rsnp_threshold=0.40,
        shareholder_lookback_quarters=4, # Point-to-Point
        rsi_threshold=40,
        rsi_exit_threshold=39
    )
    
    # 3. Setup Portfolio for Backtest Validation
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 4. Define Rebalance Dates
    rebalance_dates = []
    all_trading_dates = dh.get_all_dates()
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            # Find closest trading day <= 15th
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid:
                rebalance_dates.append(max(valid))
    
    # 5. Run Validation Backtest (2017 - Feb 2026)
    print("Running Final Strategy Backtest (Champion Baseline)...")
    engine.run(
        start_date="2017-05-15", 
        end_date="2026-02-05", 
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 6. Print Performance Confirmation
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    print("\n" + "="*50)
    print("FINAL STRATEGY PERFORMANCE (CONFIRMED)")
    print("="*50)
    print(f"Absolute Return     : {stats['Absolute Return']}")
    print(f"CAGR                : {stats['CAGR']}")
    print(f"Max Drawdown        : {stats['Max Drawdown']}")
    print(f"Sharpe Ratio        : {stats['Sharpe Ratio']}")
    print(f"Final NAV           : ₹{portfolio.nav_history[-1]['nav']:,.0f}")
    print("="*50)

    # 7. GENERATE FEB 2026 REBALANCE LIST
    print("\nGenerating Final Rebalance List for Feb 15, 2026...")
    target_date = pd.Timestamp("2026-02-15")
    # Get actual trading date for rebalance
    actual_reb_date = max([dt for dt in all_trading_dates if dt <= target_date])
    
    final_picks = strategy.calculate_selection(actual_reb_date)
    
    if final_picks:
        picks_df = pd.DataFrame([
            {"ISIN": isin, "Weight": weight, "Industry": dh.isin_to_industry.get(isin)}
            for isin, weight in final_picks.items()
        ])
        # Add metadata
        picks_df['Company'] = picks_df['ISIN'].map(dh.isin_to_name)
        picks_df = picks_df[['Company', 'ISIN', 'Industry', 'Weight']]
        
        output_path = repo_root / "outputs" / "final_rebalance_feb_2026.csv"
        output_path.parent.mkdir(exist_ok=True)
        picks_df.to_csv(output_path, index=False)
        print(f"\nSUCCESS: Final Feb 2026 Rebalance list saved to: {output_path}")
        print("\nTOP PICKS (Feb 2026):")
        print(picks_df.to_string(index=False))
    else:
        print("\nERROR: No picks generated for Feb 2026. Check data availability.")

if __name__ == "__main__":
    generate_final_rebalance()
