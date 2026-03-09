import pandas as pd
import warnings
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics

class AccruedTaxManager:
    """
    Variation: Accrues tax liability throughout the Financial Year (April-March).
    Supports Multi-Year Loss Carry-Forward by tracking net tax impact.
    Settles (deducts) the full amount only during the February rebalance.
    Post-Feb rebalance exits (mid-Feb to March end) are settled immediately.
    """
    def __init__(self, stcg_rate: float = 0.20, ltcg_rate: float = 0.125):
        self.stcg_rate = stcg_rate
        self.ltcg_rate = ltcg_rate
        self.tax_impact_ledger = 0.0 # Lifetime net tax liability (can be negative)
        self.tax_paid_history = []
        
    def process_realized_gains(self, date: pd.Timestamp, stcg_base: float, ltcg_base: float) -> float:
        """Logs gains/losses to the ledger and determines immediate settlement."""
        tax_impact = (stcg_base * self.stcg_rate) + (ltcg_base * self.ltcg_rate)
        self.tax_impact_ledger += tax_impact
        
        # Determine if we are in the "Immediate Settlement Window" 
        # (Post mid-Feb rebalance to March 31)
        is_late_fy = (date.month == 2 and date.day >= 16) or (date.month == 3)
        
        if is_late_fy and self.tax_impact_ledger > 0:
            # Settle net liability immediately for late-FY exits
            to_pay = self.tax_impact_ledger
            self.tax_impact_ledger = 0.0
            self.tax_paid_history.append({'date': date, 'amount': to_pay, 'type': 'immediate_late_fy'})
            return to_pay
        elif is_late_fy and self.tax_impact_ledger < 0:
            # If we are in the late window but have a net loss, 
            # we don't return cash to the portfolio (real-world taxes don't give refunds like this),
            # but we keep the negative balance for next year.
            return 0.0
        else:
            # Normal period: Just accrue to the ledger
            return 0.0

    def settle_accrued_tax(self, date: pd.Timestamp) -> float:
        """Called during Feb rebalance to pay out the accumulated net liability."""
        if self.tax_impact_ledger > 0:
            total_to_pay = self.tax_impact_ledger
            self.tax_impact_ledger = 0.0 # Reset since we paid it off
            self.tax_paid_history.append({'date': date, 'amount': total_to_pay, 'type': 'annual_settlement'})
            return total_to_pay
        else:
            # If ledger is negative, carry the loss forward to next year
            return 0.0

def run_accrued_tax_backtest():
    repo_root = Path(__file__).parent
    
    # 1. Setup Data
    print("Initializing DataHandler...")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    all_dates = dh.get_all_dates()
    quarterly_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in quarterly_dates:
                        quarterly_dates.append(reb)
    quarterly_dates.sort()
    
    warnings.filterwarnings('ignore')
    fee_model = FeeModel(0.0015, 0.005)
    
    # --- Execute Backtest with Accrued Tax Logic ---
    print("\n--- Running Accrued Tax Variation (Settlement in Feb) ---")
    port = Portfolio(10000000)
    strategy = ContrarianBreadthStrategy(dh, min_history_years=0.0)
    strategy.precompute_rsi(quarterly_dates)
    
    tax_man = AccruedTaxManager(0.20, 0.125)
    sim = SimEngine(dh, port, fee_model, tax_man)
    
    # Custom Loop to handle Feb Settle
    current_idx = 0
    sim_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
    
    for today in sim_dates:
        # Check Portfolio Health
        if port.cash < 0 and port.get_market_value(dh.get_daily_prices(today)) + port.cash < 0:
            print(f"CRITICAL: Portfolio Bankrupt on {today}")
            break
            
        # 1. Check Technical Exits (Post-Feb Rebalance ones settle immediately)
        exits = strategy.check_exits(today, port.holdings)
        if exits:
            prices = dh.get_daily_prices(today)
            if prices:
                for isin in exits:
                    sim._sell_all(isin, today, prices)
            
        # 2. Check Rebalance
        if today in quarterly_dates:
            # SPECIAL LOGIC: If this is the February rebalance, settle accrued taxes FIRST
            if today.month == 2:
                annual_tax = tax_man.settle_accrued_tax(today)
                if annual_tax != 0:
                    port.cash -= annual_tax
                    print(f"Settled Annual Accrued Tax on {today.date()}: ₹{annual_tax:,.0f}")
            
            # Normal Rebalance
            prices = dh.get_daily_prices(today)
            if prices:
                new_target = strategy.calculate_selection(today)
                sim._execute_rebalance(today, new_target, prices)
            
        # 3. Daily NAV Log
        port.record_nav(today, dh.get_daily_prices(today))
        
    nav_df = pd.DataFrame(port.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print(f"ACCRUED TAX VARIATION PERFORMANCE (2017 - 2026)")
    print("="*60)
    print(f"CAGR: {stats['CAGR']}")
    print(f"Sharpe Ratio: {stats['Sharpe Ratio']}")
    print(f"Max Drawdown: {stats['Max Drawdown']}")
    print("="*60)

if __name__ == "__main__":
    run_accrued_tax_backtest()
