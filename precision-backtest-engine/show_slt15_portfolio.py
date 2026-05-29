"""Show what SLT15 would select if starting today."""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.slt15_strategy import SLT15Strategy

REPO = Path(__file__).parent

def main():
    dh = DataHandler(REPO / "database/price_data.parquet")
    dh.load_data()
    all_dates = dh.get_all_dates()

    today = pd.Timestamp("2026-05-14")
    actual_date = max(d for d in all_dates if d <= today)
    print(f"Signal date: {actual_date.date()}")

    strategy = SLT15Strategy(dh)

    # Show qualified industries
    qualified = strategy.get_qualified_industries(actual_date)
    print(f"\nQualified industries ({len(qualified)}):")
    for ind in qualified:
        print(f"  - {ind}")

    # Get selection
    selection = strategy.calculate_selection(actual_date)
    if not selection:
        print("\nNo stocks selected!")
        return

    print(f"\nSLT15 Portfolio ({len(selection)} stocks):")
    print(f"{'Stock':<30} {'ISIN':<15} {'Industry':<30} {'Weight':>8}")
    print("-" * 85)

    stats_df = pd.read_parquet(REPO / "database/stock_statistics.parquet")
    isin_to_name = stats_df.set_index('isin')['company_name'].to_dict()

    # Get current prices
    prices = dh.get_daily_prices(actual_date)

    by_industry = {}
    for isin, weight in selection.items():
        ind = dh.isin_to_industry.get(isin, 'Unknown')
        name = isin_to_name.get(isin, isin)
        if ind not in by_industry:
            by_industry[ind] = []
        by_industry[ind].append((name, isin, weight))

    for ind in by_industry:
        for name, isin, weight in by_industry[ind]:
            print(f"{name:<30} {isin:<15} {ind:<30} {weight*100:>7.2f}%")
        print()

    total_weight = sum(selection.values())
    print(f"{'Total':<30} {'':15} {'':30} {total_weight*100:>7.2f}%")


if __name__ == "__main__":
    main()
