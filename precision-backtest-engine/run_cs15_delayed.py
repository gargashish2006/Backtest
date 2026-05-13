import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_delayed_strategy import CS15DelayedStrategy
from utils.analytics import calculate_metrics

REPO_ROOT = Path(__file__).parent


def run_cs15_delayed():
    dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(REPO_ROOT / "benchmarks")

    start_date = "2017-05-15"
    end_date = "2026-03-06"

    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            if d > pd.Timestamp(end_date):
                continue
            v = [dt for dt in all_dates if dt <= d]
            if v:
                rdates.append(max(v))
    rdates = sorted(set([d for d in rdates if d >= pd.Timestamp(start_date)]))

    strategy = CS15DelayedStrategy(dh)
    strategy.precompute_rsi(rdates)

    portfolio = Portfolio(10_000_000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_manager = TaxManager(0.20, 0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_manager,
                       cash_yield_rate=0.05, cash_tax_rate=0.30)

    print("Running CS15_delayed Backtest...")
    engine.run(start_date, end_date, strategy.calculate_selection, rdates, verbose=False)

    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)

    print("\n" + "=" * 40)
    print("CS15_DELAYED STRATEGY PERFORMANCE")
    print("=" * 40)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("=" * 40)

    nav_df.to_csv(REPO_ROOT / "cs15_delayed_nav.csv", index=False)
    print("NAV saved to cs15_delayed_nav.csv")


if __name__ == "__main__":
    run_cs15_delayed()
