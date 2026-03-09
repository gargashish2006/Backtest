
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from research_quadrants import QuadrantStrategy
from utils.analytics import calculate_metrics

def run_long_short_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_trading_dates = dh.get_all_dates()
    
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_trading_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))

    # 1. Run Long Leg (Champion)
    print("\nRunning Long Leg (Top/High/High)...")
    long_strategy = QuadrantStrategy(
        dh, group_mode='top', industry_mode='high', rsnp_mode='high',
        num_stocks=15, max_per_industry=3, rsnp_threshold=0.40
    )
    long_portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    long_engine = SimEngine(dh, long_portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    long_engine.run(start_date="2017-05-15", end_date="2026-02-05", 
                    strategy_func=long_strategy.calculate_selection, rebalance_dates=rebalance_dates, verbose=False)
    
    long_nav = pd.DataFrame(long_portfolio.nav_history).set_index('date')['nav']

    # 2. Run Short Leg (Failure Regime) - 6 Stocks
    print("Running Short Leg (Bottom/Low/Low) - 6 Stocks...")
    short_strategy = QuadrantStrategy(
        dh, group_mode='bottom', industry_mode='low', rsnp_mode='low',
        num_stocks=6, max_per_industry=3, rsnp_threshold=0.40
    )
    short_portfolio = Portfolio(initial_cash=10000000)
    short_engine = SimEngine(dh, short_portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    short_engine.run(start_date="2017-05-15", end_date="2026-02-05", 
                     strategy_func=short_strategy.calculate_selection, rebalance_dates=rebalance_dates, verbose=False)
    
    short_nav = pd.DataFrame(short_portfolio.nav_history).set_index('date')['nav']

    # 3. Calculate 21-Stock Equal Capital Performance
    print("Calculating Combined 21-Stock Equal Capital Performance...")
    # Daily Returns
    long_rets = long_nav.pct_change().fillna(0)
    short_rets = short_nav.pct_change().fillna(0)
    
    # Portfolio Return (15 Longs, 6 Shorts, Each 1/21 weight)
    # R = (15/21)*R_long - (6/21)*R_short
    portfolio_rets = (15/21) * long_rets - (6/21) * short_rets
    
    # Compounded Portfolio NAV
    combined_nav = (1 + portfolio_rets).cumprod() * 10000000
    
    # 4. Visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [2, 1]})
    
    ax1.plot(long_nav.index, long_nav.values / 1e7, label='Champion Long-Only (15 Stocks)', color='green', alpha=0.5)
    ax1.plot(combined_nav.index, combined_nav.values / 1e7, label='21-Stock Equal Capital LS (15L / 6S)', color='blue', linewidth=2)
    
    ax1.set_title("Long-Short Strategy: 21-Stock Equal Capital Model", fontsize=16)
    ax1.set_ylabel("NAV (Scaled to 1.0)", fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Drawdown comparison
    def get_dd(nav_series):
        return (nav_series / nav_series.cummax() - 1)
        
    ax2.fill_between(long_nav.index, 0, get_dd(long_nav), color='green', alpha=0.1, label='Long-Only Drawdown')
    ax2.plot(combined_nav.index, get_dd(combined_nav), color='blue', label='LS Portfolio Drawdown')
    ax2.set_ylabel("Drawdown %", fontsize=12)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    chart_path = repo_root / "outputs/long_short_21stock_analysis.png"
    plt.savefig(chart_path, dpi=300)
    print(f"\n21-Stock LS Chart saved to: {chart_path}")
    
    # 5. Metrics Comparison
    combined_metrics = calculate_metrics(pd.DataFrame({'date': combined_nav.index, 'nav': combined_nav.values}))
    long_metrics = calculate_metrics(pd.DataFrame({'date': long_nav.index, 'nav': long_nav.values}))
    short_metrics = calculate_metrics(pd.DataFrame({'date': short_nav.index, 'nav': short_nav.values}))
    
    print("\n" + "="*60)
    print("21-STOCK EQUAL CAPITAL PERFORMANCE (15L / 6S)")
    print("="*60)
    print(f"Strategy          | CAGR   | Max DD | Sharpe")
    print(f"------------------|--------|--------|-------")
    print(f"Champion Long-Only| {long_metrics['CAGR']:<6} | {long_metrics['Max Drawdown']:<6} | {long_metrics['Sharpe Ratio']:<5}")
    print(f"21-Stock LS Port  | {combined_metrics['CAGR']:<6} | {combined_metrics['Max Drawdown']:<6} | {combined_metrics['Sharpe Ratio']:<5}")
    print("="*60)
    print(f"Net-Long Exposure: ~42.8%")
    print(f"Gross Exposure: 100%")
    print("="*60)

if __name__ == "__main__":
    run_long_short_analysis()
