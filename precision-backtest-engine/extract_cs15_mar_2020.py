
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy

def extract_portfolio():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    target_date = "2020-03-30"
    
    all_dates = dh.get_all_dates()
    rdates = []
    for y in range(2017, 2021):
        for m in [2, 5, 8, 11]:
            d = pd.Timestamp(year=y, month=m, day=15)
            v = [dt for dt in all_dates if dt <= d]
            if v: rdates.append(max(v))
    rdates = sorted([d for d in rdates if d >= pd.Timestamp(start_date) and d <= pd.Timestamp(target_date)])

    # 1. Setup Strategy
    strategy = CS15Strategy(dh)
    strategy.precompute_rsi(rdates)
    
    # 2. Setup Simulation
    portfolio = Portfolio(10000000)
    fee_model = FeeModel(0.0015, 0.005)
    tax_manager = TaxManager(0.20, 0.125)
    
    engine = SimEngine(dh, portfolio, fee_model, tax_manager, 
                        cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    # 3. Run until target date
    print(f"Running CS15 until {target_date}...")
    engine.run(start_date, target_date, strategy.calculate_selection, rdates, verbose=False)
    
    # 4. Extract Holdings
    prices = dh.get_daily_prices(pd.Timestamp(target_date))
    if not prices:
        # If target_date is not a trading day, get the last one
        last_date = max([d for d in all_dates if d <= pd.Timestamp(target_date)])
        prices = dh.get_daily_prices(last_date)
        print(f"Target date was not a trading day. Using {last_date.date()} instead.")
    
    holdings = []
    for isin, lots in portfolio.holdings.items():
        qty = sum(lot.remaining_qty for lot in lots)
        if qty > 0:
            price = prices.get(isin, 0)
            name = dh.isin_to_name.get(isin, "Unknown")
            industry = dh.isin_to_industry.get(isin, "Unknown")
            val = qty * price
            holdings.append({
                "ISIN": isin,
                "Company": name,
                "Industry": industry,
                "Quantity": qty,
                "Value": val
            })
    
    df = pd.DataFrame(holdings)
    if not df.empty:
        total_value = df['Value'].sum()
        df['Weight (%)'] = (df['Value'] / (total_value + portfolio.cash) * 100).round(2)
        print("\n" + "="*60)
        print(f"CS15 PORTFOLIO HOLDINGS ON {target_date}")
        print("="*60)
        print(df.sort_values('Value', ascending=False).to_string(index=False))
        print("="*60)
        print(f"Total Portfolio Value: {total_value + portfolio.cash:,.2f}")
        print(f"Cash Balance       : {portfolio.cash:,.2f}")
        print(f"Equity Value       : {total_value:,.2f}")
    else:
        print(f"\nNo holdings found on {target_date}. Portfolio is in 100% Cash.")
        print(f"Cash Balance: {portfolio.cash:,.2f}")

if __name__ == "__main__":
    extract_portfolio()
