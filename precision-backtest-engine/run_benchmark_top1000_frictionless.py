
import pandas as pd
import warnings
from typing import Dict
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from utils.analytics import calculate_metrics

class Top1000FrictionlessStrategy:
    """
    Top 1000 Universe (Liquid), Equal Weighted.
    NO COSTS. NO TAXES.
    """
    def __init__(self, data_handler: DataHandler):
        self.dh = data_handler
        
    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        # 1. Calculation dates
        calc_date = date - pd.Timedelta(days=7)
        all_dates = self.dh.get_all_dates()
        if not all_dates: return {}
        
        actual_calc_date = max([d for d in all_dates if d <= calc_date])
        
        # 2. Get Universe
        metrics = self.dh.get_daily_metrics(actual_calc_date)
        if metrics.empty: return {}
        
        # Top 1000 by Market Cap
        universe = metrics.sort_values('mc', ascending=False).head(1000)
        isins = universe['isin'].tolist()
        
        if not isins: return {}
        
        # 3. Equal Weighting
        w = 1.0 / len(isins)
        return {isin: w for isin in isins}

def run_frictionless_benchmark():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date, end_date = "2017-05-15", "2026-05-13"
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    
    # Quarterly Rebalance for Index Tracking
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date): rebalance_dates.append(reb)
    rebalance_dates = sorted(list(set(rebalance_dates)))

    print("Running Top 1000 FRICTIONLESS Benchmark (0% Cost, 0% Tax)...")
    warnings.filterwarnings('ignore')

    strat = Top1000FrictionlessStrategy(dh)
    port = Portfolio(10000000)
    
    # ZERO COSTS, ZERO TAXES
    fee_model = FeeModel(transaction_fee_rate=0.0, impact_cost_rate=0.0)
    tax_man = TaxManager(stcg_rate=0.0, ltcg_rate=0.0) # Tax rates 0%
    
    # Cash Yield 0% to be pure price index? Or keep it?
    # Usually benchmarks are Total Return Indices, so cash drag is minimal but reinvestment happens.
    # Let's keep cash yield at 0% to simulate pure equity exposure and avoid "risk free rate" padding.
    # Actually, a TR index assumes dividends are reinvested. We don't have dividends. 
    # But cash held during rebalance (if any) should probably not earn interest to be "frictionless"?
    # Let's keep specific cash parameters to 0 to be safe.
    
    eng = SimEngine(dh, port, fee_model, tax_man, cash_yield_rate=0.0, cash_tax_rate=0.0)
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    nav_df = pd.DataFrame(port.nav_history)
    nav_df.to_csv(repo_root / "outputs/top1000_frictionless_nav.csv", index=False)

    # Build benchmark parquet (index_value = NAV normalised to start at 1)
    bench_df = nav_df[['date', 'nav']].copy()
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    bench_df = bench_df.sort_values('date').reset_index(drop=True)
    base = bench_df['nav'].iloc[0]
    bench_df['index_value'] = bench_df['nav'] / base * 1000   # start at 1000
    bench_df['daily_return'] = bench_df['nav'].pct_change().fillna(0)
    bench_df['cumulative_return'] = (bench_df['nav'] / base - 1) * 100
    bench_df['num_stocks'] = 1000
    bench_df = bench_df[['date', 'index_value', 'num_stocks', 'daily_return', 'cumulative_return']]
    bench_df.to_parquet(repo_root / "benchmarks/Benchmark_1000_equalWeight.parquet", index=False)
    bench_df.to_parquet(repo_root / f"benchmarks/benchmark_top1000_equal_weight_2016-02-01_to_2026-05-13.parquet", index=False)
    print(f"Benchmark parquet saved: {len(bench_df)} rows, {bench_df['date'].min().date()} to {bench_df['date'].max().date()}")

    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("TOP 1000 FRICTIONLESS BENCHMARK")
    print("="*60)
    print(f"{'CAGR':<20} : {stats['CAGR']}")
    print(f"{'Max Drawdown':<20} : {stats['Max Drawdown']}")
    print(f"{'Sharpe Ratio':<20} : {stats['Sharpe Ratio']}")
    print("="*60)
    print(f"Final NAV: {port.nav_history[-1]['nav']:,.2f}")
    print(f"Total Costs: {eng.fee_model.total_fees:,.2f}")
    print(f"Total Taxes: {sum(t['total_tax'] for t in eng.tax_man.tax_paid_history):,.2f}")
    print("="*60)

if __name__ == "__main__":
    run_frictionless_benchmark()
