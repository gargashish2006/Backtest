"""
CS15 RSNP sweep: 9 Nifty indices x 5 thresholds = 45 backtests.

Loads data once, precomputes RSI once, then loops over (benchmark, threshold)
running a fresh portfolio/engine each time.
"""
import sys
import time
import pandas as pd
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy

INDICES = [
    'NIFTY 50',
    'NIFTY 100',
    'NIFTY 200',
    'NIFTY 500',
    'NIFTY MIDCAP 100',
    'NIFTY MIDCAP 150',
    'NIFTY SMALLCAP 100',
    'NIFTY SMALLCAP 250',
    'NIFTY LARGEMID250',
]
THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50]

START_DATE = "2017-05-15"
END_DATE = "2026-03-06"


def metrics_from_nav(nav_df: pd.DataFrame) -> dict:
    if nav_df.empty:
        return {}
    initial = nav_df.iloc[0]['nav']
    final = nav_df.iloc[-1]['nav']
    years = (nav_df.iloc[-1]['date'] - nav_df.iloc[0]['date']).days / 365.25
    cagr = (final / initial) ** (1 / years) - 1 if years > 0 else 0
    peak = nav_df['nav'].cummax()
    dd = (nav_df['nav'] - peak) / peak
    max_dd = dd.min()
    daily_ret = nav_df['nav'].pct_change().dropna()
    rf_daily = (1.06) ** (1 / 252) - 1
    excess = daily_ret - rf_daily
    sharpe = (excess.mean() / excess.std()) * (252 ** 0.5) if excess.std() else 0.0
    return {
        'abs_return_pct': (final / initial - 1) * 100,
        'cagr_pct': cagr * 100,
        'max_dd_pct': max_dd * 100,
        'sharpe': sharpe,
        'final_nav': final,
    }


def build_rdates(all_dates, start_date, end_date):
    rdates = []
    for y in range(2017, 2027):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            if d > pd.Timestamp(end_date):
                continue
            v = [dt for dt in all_dates if dt <= d]
            if v:
                rdates.append(max(v))
    return sorted(set([d for d in rdates if d >= pd.Timestamp(start_date)]))


def main():
    print(f"Loading data from {REPO_ROOT}...")
    dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(REPO_ROOT / "benchmarks")

    loaded = list(getattr(dh, 'indices_bench', {}).keys())
    print(f"Loaded indices: {loaded}")
    missing = [i for i in INDICES if i not in loaded]
    if missing:
        print(f"WARNING: missing indices in data: {missing}")

    all_dates = dh.get_all_dates()
    rdates = build_rdates(all_dates, START_DATE, END_DATE)
    print(f"Rebalance dates: {len(rdates)}")

    strategy = CS15Strategy(dh)
    strategy.precompute_rsi(rdates)

    results = []
    total = len(INDICES) * len(THRESHOLDS)
    run_idx = 0
    t_start = time.time()

    for index_name in INDICES:
        if index_name not in loaded:
            continue
        for thr in THRESHOLDS:
            run_idx += 1
            tag = f"[{run_idx}/{total}] {index_name} @ {thr:.2f}"
            print(f"\n{tag}")
            t0 = time.time()

            strategy.rsnp_benchmark = index_name
            strategy.rsnp_threshold = thr

            portfolio = Portfolio(10_000_000)
            fee_model = FeeModel(0.0015, 0.005)
            tax_manager = TaxManager(0.20, 0.125)
            engine = SimEngine(dh, portfolio, fee_model, tax_manager,
                               cash_yield_rate=0.05, cash_tax_rate=0.30)
            engine.run(START_DATE, END_DATE, strategy.calculate_selection, rdates, verbose=False)

            nav_df = pd.DataFrame(portfolio.nav_history)
            m = metrics_from_nav(nav_df)
            m['index'] = index_name
            m['rsnp_threshold'] = thr
            m['runtime_sec'] = round(time.time() - t0, 1)
            results.append(m)
            print(f"  CAGR {m['cagr_pct']:.2f}%  MDD {m['max_dd_pct']:.2f}%  "
                  f"Sharpe {m['sharpe']:.2f}  ({m['runtime_sec']}s)")

    elapsed = time.time() - t_start
    print(f"\nAll runs done in {elapsed/60:.1f} min")

    df = pd.DataFrame(results)[['index', 'rsnp_threshold', 'cagr_pct',
                                 'abs_return_pct', 'max_dd_pct', 'sharpe',
                                 'final_nav', 'runtime_sec']]
    out_csv = REPO_ROOT / "outputs" / "cs15_rsnp_indices_sweep.csv"
    out_csv.parent.mkdir(exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")

    print("\n" + "=" * 70)
    print("CS15 RSNP SWEEP — CAGR % (rows=index, cols=threshold)")
    print("=" * 70)
    pivot = df.pivot(index='index', columns='rsnp_threshold', values='cagr_pct')
    pivot = pivot.reindex([i for i in INDICES if i in pivot.index])
    print(pivot.round(2).to_string())

    print("\nSharpe ratio pivot:")
    sh_pivot = df.pivot(index='index', columns='rsnp_threshold', values='sharpe')
    sh_pivot = sh_pivot.reindex([i for i in INDICES if i in sh_pivot.index])
    print(sh_pivot.round(2).to_string())

    print("\nMax Drawdown % pivot:")
    dd_pivot = df.pivot(index='index', columns='rsnp_threshold', values='max_dd_pct')
    dd_pivot = dd_pivot.reindex([i for i in INDICES if i in dd_pivot.index])
    print(dd_pivot.round(2).to_string())


if __name__ == "__main__":
    main()
