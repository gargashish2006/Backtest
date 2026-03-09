
import pandas as pd
from typing import Dict, List, Callable
from pathlib import Path
from datetime import datetime
from engine.sim_engine import SimEngine
from engine.accounting import TaxManager, FeeModel
from engine.portfolio import Portfolio
from data.data_handler import DataHandler
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics
import inspect

# -----------------------------------------------------------------------------
# FY Tax Manager
# -----------------------------------------------------------------------------
class FYTaxManager(TaxManager):
    """
    Manages taxes on an Accrual basis (April 1 to March 31).
    Gains/Losses are accumulated through the year.
    Net tax is calculated and paid at the end of the Financial Year.
    """
    def __init__(self, stcg_rate: float = 0.20, ltcg_rate: float = 0.125, ltcg_exemption: float = 125000):
        super().__init__(stcg_rate, ltcg_rate, ltcg_exemption)
        # Track FY accumulated gains/losses
        self.fy_stcg = 0.0
        self.fy_ltcg = 0.0
        
        # Track Carry Forward Losses (simplification: assume we can use them next year)
        self.cf_stcl = 0.0
        self.cf_ltcl = 0.0

    def process_realized_gains(self, date: pd.Timestamp, stcg_base: float, ltcg_base: float) -> float:
        """Accumulate gains, do NOT deduct tax immediately."""
        self.fy_stcg += stcg_base
        self.fy_ltcg += ltcg_base
        return 0.0 # No tax paid immediately

    def settle_fy_taxes(self, date: pd.Timestamp) -> float:
        """Calculate net tax liability for the year, applying set-off rules."""
        
        # 1. Apply Carry Forward Losses
        net_st = self.fy_stcg - self.cf_stcl
        net_lt = self.fy_ltcg - self.cf_ltcl
        
        # Reset CF (consumed or re-calculated below)
        self.cf_stcl = 0.0
        self.cf_ltcl = 0.0
        
        # 2. Intra-Year Set Off (Indian Context)
        # ST Loss can offset LT Gain? No. 
        # Wait, ST Loss can offset ST Gain. 
        # LT Loss can offset LT Gain.
        # ST Loss can offset LT Gain? No.
        # LT Loss can offset ST Gain? No.
        # Actually: ST Loss -> Both ST and LT gains. LT Loss -> Only LT gains.
        
        # Logic:
        # If Current ST is Negative (Loss):
        if net_st < 0:
            st_loss = abs(net_st)
            net_st = 0.0
            # Offset against LT Gain
            if net_lt > 0:
                offset = min(st_loss, net_lt)
                net_lt -= offset
                st_loss -= offset
            
            # Remaining ST Loss carried forward
            self.cf_stcl = st_loss
            
        # If Current LT is Negative (Loss):
        if net_lt < 0:
            lt_loss = abs(net_lt)
            net_lt = 0.0
            # LT Loss CANNOT offset ST Gain. Carry forward.
            self.cf_ltcl = lt_loss
            
        # 3. Calculate Tax
        tax_st = max(0, net_st * self.stcg_rate)
        # LT Exemption
        taxable_lt = max(0, net_lt - self.ltcg_exemption)
        tax_lt = taxable_lt * self.ltcg_rate
        
        total_tax = tax_st + tax_lt
        
        # Reset FY counters
        self.fy_stcg = 0.0
        self.fy_ltcg = 0.0
        
        if total_tax > 0:
            self.tax_paid_history.append({
                'date': date,
                'type': 'FY_Settlement',
                'amount': total_tax
            })
            
        return total_tax

# -----------------------------------------------------------------------------
# FY Sim Engine
# -----------------------------------------------------------------------------
class FYSimEngine(SimEngine):
    def run(self, start_date: str, end_date: str, 
            strategy_func: Callable[[pd.Timestamp], List[str]],
            rebalance_dates: List[pd.Timestamp],
            verbose: bool = True):
        
        super_run_source = inspect.getsource(SimEngine.run)
        # We can't easily rely on super().run because we need to inject the FY check inside the loop.
        # So we duplicate the loop logic but insert the check.
        
        all_dates = self.dh.get_all_dates()
        mask = (pd.to_datetime(all_dates) >= pd.to_datetime(start_date)) & \
               (pd.to_datetime(all_dates) <= pd.to_datetime(end_date))
        sim_dates = [d for d, m in zip(all_dates, mask) if m]
        if not sim_dates: return

        if verbose:
            print(f"Starting FY Tax Simulation from {sim_dates[0].date()} to {sim_dates[-1].date()}...")
        target_portfolio = []

        # Helper to get FY
        def get_fy(d):
            return d.year if d.month < 4 else d.year + 1

        current_fy = get_fy(sim_dates[0])

        for i, date in enumerate(sim_dates):
            prices = self.dh.get_daily_prices(date)
            if not prices: continue
            
            self._accrue_interest(date)
            self.portfolio.record_nav(date, prices)

            # FY Check: If tomorrow is new FY, settle taxes today (conceptually)
            # Or simpler: check if FY changed vs variable
            step_fy = get_fy(date)
            if step_fy > current_fy:
                # FY ended. Settle taxes.
                tax = self.tax_man.settle_fy_taxes(date)
                self.portfolio.cash -= tax
                current_fy = step_fy
                if verbose: print(f"FY {current_fy-1} Ended. Tax Paid: {tax:.2f}")

            # Rebalance
            if date in rebalance_dates:
                target_portfolio = strategy_func(date)
                self._execute_rebalance(date, target_portfolio, prices)
            else:
                # Check Exits logic (manual copy from SimEngine to ensure correctness)
                if hasattr(strategy_func, '__self__') and hasattr(strategy_func.__self__, 'check_exits'):
                    if self.portfolio.holdings:
                        exits = strategy_func.__self__.check_exits(date, list(self.portfolio.holdings.keys()))
                        if exits:
                            for isin in exits:
                                self._sell_all(isin, date, prices)
        
        # Settle final year taxes at end of sim
        final_tax = self.tax_man.settle_fy_taxes(sim_dates[-1])
        self.portfolio.cash -= final_tax
        if verbose: print(f"Simulation Ended. Final Tax Paid: {final_tax:.2f}")


# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
def run_simulation():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")

    # Dates
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    
    # Rebalance Dates
    all_dates = dh.get_all_dates()
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid:
                reb = max(valid)
                if reb >= pd.Timestamp(start_date) and reb <= pd.Timestamp(end_date):
                    if reb not in rebalance_dates: rebalance_dates.append(reb)
    rebalance_dates.sort()

    # Strategy
    strat = ContrarianBreadthStrategy(dh)
    strat.precompute_rsi(rebalance_dates)

    # Engine Setup (FY Mode)
    port = Portfolio(10000000)
    fee = FeeModel(0.0015, 0.005)
    tax = FYTaxManager(0.20, 0.125) # Default Rates
    
    # Use 0.98 NAV buffer via inheritance (SimEngine._execute_rebalance uses it)
    engine = FYSimEngine(dh, port, fee, tax, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    print("\nRunning FY Accrual Tax Simulation...")
    engine.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=True)
    
    stats = calculate_metrics(pd.DataFrame(port.nav_history))
    
    print("\n" + "="*60)
    print("FY TAX SIMULATION RESULTS")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
    print("="*60)

if __name__ == "__main__":
    run_simulation()
