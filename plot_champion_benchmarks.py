import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy

def plot_champion_with_benchmarks():
    # 1. Setup Data Paths
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(base_path / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(base_path / "benchmarks")
    
    # 2. Setup Champion Strategy (RSNP 0.40)
    strategy = ContrarianBreadthStrategy(dh, rsnp_threshold=0.40)
    
    # 3. Setup Simulation Engine
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # Quarterly Rebalance Dates
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    # 4. Run Strategy
    engine.run(
        start_date="2017-05-15",
        end_date="2026-02-05",
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates,
        verbose=False
    )
    
    strategy_nav = pd.DataFrame(portfolio.nav_history)
    strategy_nav['date'] = pd.to_datetime(strategy_nav['date'])
    strategy_nav = strategy_nav.set_index('date')['nav']
    
    # 5. Load Benchmarks
    bench_dir = base_path / "benchmarks"
    
    def load_bench(filename, label):
        df = pd.read_parquet(bench_dir / filename)
        df['date'] = pd.to_datetime(df['date'])
        # Filter to same period
        df = df[(df['date'] >= strategy_nav.index.min()) & (df['date'] <= strategy_nav.index.max())]
        # Normalize to 1 Cr
        initial_val = df.sort_values('date').iloc[0]['index_value']
        df['nav'] = (df['index_value'] / initial_val) * 10000000
        return df.set_index('date')['nav']

    b100 = load_bench("Benchmark_100_equalWeight.parquet", "Top 100")
    b500 = load_bench("Benchmark_500_equalWeight.parquet", "Top 500")
    b1000 = load_bench("Benchmark_1000_equalWeight.parquet", "Top 1000")
    
    # 6. Plotting
    plt.figure(figsize=(15, 8), dpi=120)
    plt.style.use('dark_background') # Aesthetic choice for WOW factor
    
    plt.plot(strategy_nav.index, strategy_nav / 1e7, label='Contrarian Breadth Champion (Post-Tax)', color='#00FFCC', linewidth=2.5)
    plt.plot(b1000.index, b1000 / 1e7, label='Top 1000 Equal Weight', color='#FF9900', alpha=0.7, linestyle='--')
    plt.plot(b500.index, b500 / 1e7, label='Top 500 Equal Weight', color='#FFD700', alpha=0.5, linestyle=':')
    plt.plot(b100.index, b100 / 1e7, label='Top 100 Equal Weight', color='#C0C0C0', alpha=0.5, linestyle='-.')
    
    plt.title("Contrarian Breadth Champion vs. Market Benchmarks", fontsize=16, fontweight='bold', pad=20)
    plt.ylabel("Growth of 1 Crore (in Cr)", fontsize=12)
    plt.xlabel("Year", fontsize=12)
    plt.grid(True, which='both', linestyle='--', alpha=0.3)
    plt.legend(loc='upper left', fontsize=10)
    
    # Add final value annotations
    final_strat = strategy_nav.iloc[-1] / 1e7
    plt.annotate(f'₹{final_strat:.2f} Cr', 
                 xy=(strategy_nav.index[-1], final_strat),
                 xytext=(10, 0), textcoords='offset points', color='#00FFCC', fontweight='bold')

    plt.tight_layout()
    plot_path = base_path / "outputs/champion_vs_benchmarks.png"
    plt.savefig(plot_path)
    print(f"Comparison plot saved to {plot_path}")
    
    # Print numerical comparison
    print("\nNumerical Outperformance Table (Final Value of 1 Cr):")
    print(f"{'Strategy':<30} | {'Final Value':<15} | {'Alpha vs Top 1000':<15}")
    print("-" * 65)
    alpha = (strategy_nav.iloc[-1] - b1000.iloc[-1]) / 1e5
    print(f"{'Contrarian Breadth Champ':<30} | ₹{strategy_nav.iloc[-1]/1e7:>8.2f} Cr | +₹{alpha:>8.0f} L")
    print(f"{'Top 1000 Benchmark':<30} | ₹{b1000.iloc[-1]/1e7:>8.2f} Cr | --")
    print(f"{'Top 500 Benchmark':<30} | ₹{b500.iloc[-1]/1e7:>8.2f} Cr | --")
    print(f"{'Top 100 Benchmark':<30} | ₹{b100.iloc[-1]/1e7:>8.2f} Cr | --")

if __name__ == "__main__":
    plot_champion_with_benchmarks()
