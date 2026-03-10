
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_bottom_groups import ContrarianBottomGroupsStrategy
from utils.analytics import calculate_metrics

def run_bottom_groups_variation():
    # 1. Setup Data Paths
    repo_root = Path(__file__).parent
    data_path = repo_root / "database"
    dh = DataHandler(data_path / "price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    # 2. CHAMPION CONFIG + BOTTOM 50% GROUPS
    strategy = ContrarianBottomGroupsStrategy(
        dh,
        num_stocks=15,
        max_per_industry=3,
        universe_size=1000,
        liquidity_threshold_pct=0.00005,
        industry_group_top_pct=0.50, # Means pick bottom 50% in this subclass
        industry_decrease_min_pct=0.50,
        rsnp_threshold=0.40,
        shareholder_lookback_quarters=4,
        rsi_threshold=40,
        rsi_exit_threshold=39
    )
    
    # 3. Setup Portfolio/Engine
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
    
    # 5. Run Backtest
    print("Running Bottom-50% Industry Groups Backtest...")
    engine.run(
        start_date="2017-05-15", 
        end_date="2026-02-05", 
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates
    )
    
    # 6. Reporting
    nav_df = pd.DataFrame(portfolio.nav_history)
    if not nav_df.empty:
        stats = calculate_metrics(nav_df)
        print("\n" + "="*50)
        print("BOTTOM-50% GROUPS VARIATION PERFORMANCE")
        print("="*50)
        for k, v in stats.items():
            print(f"{k:<20}: {v}")
        print(f"{'Final NAV':<20}: ₹{portfolio.nav_history[-1]['nav']:,.0f}")
        print("="*50)
        
        # Save Outputs
        output_dir = repo_root / "outputs"
        output_dir.mkdir(exist_ok=True)
        nav_df.to_csv(output_dir / "bottom_groups_variation_nav.csv", index=False)
        
        # Trade Log
        trades = pd.DataFrame(portfolio.trade_log)
        if not trades.empty:
            trades.to_csv(output_dir / "bottom_groups_variation_trades.csv", index=False)
            
        # Generate Feb 2026 Picks
        print("\nGenerating Feb 15, 2026 Rebalance Picks (Bottom-50)...")
        target_date = pd.Timestamp("2026-02-15")
        actual_reb_date = max([dt for dt in all_trading_dates if dt <= target_date])
        final_picks = strategy.calculate_selection(actual_reb_date)
        
        if final_picks:
            picks_df = pd.DataFrame([
                {"Company": dh.isin_to_name.get(isin), "ISIN": isin, "Industry": dh.isin_to_industry.get(isin), "Weight": weight}
                for isin, weight in final_picks.items()
            ])
            print("\nTOP PICKS (Feb 2026) BOTTOM-50% GROUPS:")
            print(picks_df.to_string(index=False))
            picks_df.to_csv(output_dir / "bottom_groups_rebalance_feb_2026.csv", index=False)
    else:
        print("No NAV history generated.")

if __name__ == "__main__":
    run_bottom_groups_variation()
