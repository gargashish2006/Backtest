import pandas as pd
from typing import Dict, List, Callable, Optional
from datetime import datetime
from .portfolio import Portfolio
from .accounting import FeeModel, TaxManager

class SimEngine:
    """Orchestrates the daily backtesting simulation."""
    def __init__(self, 
                 data_handler, 
                 portfolio: Portfolio, 
                 fee_model: FeeModel, 
                 tax_manager: TaxManager,
                 cash_yield_rate: float = 0.05,
                 cash_tax_rate: float = 0.30):
        self.dh = data_handler
        self.portfolio = portfolio
        self.fee_model = fee_model
        self.tax_man = tax_manager
        self.cash_yield_rate = cash_yield_rate
        self.cash_tax_rate = cash_tax_rate
        
    def run(self, start_date: str, end_date: str, 
            strategy_func: Callable[[pd.Timestamp], List[str]],
            rebalance_dates: List[pd.Timestamp],
            verbose: bool = True):
        """Runs the daily simulation loop."""
        all_dates = self.dh.get_all_dates()
        mask = (pd.to_datetime(all_dates) >= pd.to_datetime(start_date)) & \
               (pd.to_datetime(all_dates) <= pd.to_datetime(end_date))
        sim_dates = [d for d, m in zip(all_dates, mask) if m]
        if not sim_dates: return

        if verbose:
            print(f"Starting simulation from {sim_dates[0].date()} to {sim_dates[-1].date()}...")
        target_portfolio = []

        for date in sim_dates:
            prices = self.dh.get_daily_prices(date)
            if not prices: continue
            
            # New: Accrue cash interest
            self._accrue_interest(date)

            # 1. Update Portfolio Mark-to-Market
            self.portfolio.record_nav(date, prices)

            # 2. Rebalance Check
            if date in rebalance_dates:
                # Generate new signals
                target_portfolio = strategy_func(date)
                self._execute_rebalance(date, target_portfolio, prices)
            else:
                # Daily Exit Check (if strategy supports it)
                # strategy_func is a bound method, so __self__ gives the instance
                if hasattr(strategy_func, '__self__') and hasattr(strategy_func.__self__, 'check_exits'):
                    if self.portfolio.holdings:
                        # Pass list of ISINs (original behavior)
                        exits = strategy_func.__self__.check_exits(date, list(self.portfolio.holdings.keys()))
                        if exits:
                            for isin in exits:
                                self._sell_all(isin, date, prices)

    def _execute_rebalance(self, date: pd.Timestamp, target_weights: Dict[str, float], prices: Dict[str, float]):
        """Adjusts holdings to target weights (isin -> weight_fraction) using incremental trades."""
        if not target_weights:
            # If no targets, exit all positions
            for isin in list(self.portfolio.holdings.keys()):
                self._sell_all(isin, date, prices)
            return

        # 1. Total NAV for weight calculation
        # 1. Total NAV for weight calculation
        total_nav = self.portfolio.cash + self.portfolio.get_market_value(prices)
        # Aim for 98% utilization (2% cash buffer for friction/price movement)
        investable_nav = total_nav * 0.98
        drift_buffer = 0.05 # 5% relative drift allowed before trimming/adding

        # 2. SELLS Phase: Process exits and trims first
        current_isins = list(self.portfolio.holdings.keys())
        for isin in current_isins:
            price = prices.get(isin)
            if not price:
                 # Fallback to last known price to allow exit of suspended/delisted stocks
                 price = self.portfolio.last_prices.get(isin)
            if not price: continue
            
            current_qty = sum(lot.remaining_qty for lot in self.portfolio.holdings[isin])
            current_val = current_qty * price
            target_weight = target_weights.get(isin, 0.0)
            target_val = investable_nav * target_weight
            
            if target_weight == 0:
                # FULL EXIT
                self._execute_trade(isin, date, price, current_qty, is_buy=False)
            elif current_val > target_val * (1 + drift_buffer):
                # PARTIAL TRIM
                qty_to_trim = int((current_val - target_val) / price)
                if qty_to_trim > 0:
                    self._execute_trade(isin, date, price, qty_to_trim, is_buy=False)

        # 3. BUYS Phase: Process entries and additions
        for isin, target_weight in target_weights.items():
            if target_weight <= 0: continue
            price = prices.get(isin)
            if not price: continue
            
            current_qty = sum(lot.remaining_qty for lot in self.portfolio.holdings.get(isin, []))
            current_val = current_qty * price
            target_val = investable_nav * target_weight
            
            if current_val < target_val * (1 - drift_buffer):
                # ADDITION or NEW ENTRY
                shortfall_val = target_val - current_val
                # Ensure we don't exceed available cash (with safety buffer)
                buy_val = min(shortfall_val, self.portfolio.cash - 2000)
                if buy_val > 1000: # Min trade size 1k
                    # Estimate quantity including fees/impact
                    total_p = price * (1 + self.fee_model.transaction_fee_rate + self.fee_model.impact_cost_rate)
                    qty_to_buy = int(buy_val / total_p)
                    if qty_to_buy > 0:
                        self._execute_trade(isin, date, price, qty_to_buy, is_buy=True)

    def _execute_trade(self, isin: str, date: pd.Timestamp, price: float, qty: int, is_buy: bool):
        """Helper to execute a trade, update accounting and tax."""
        val = qty * price
        fees = self.fee_model.calculate_costs(val, is_buy=is_buy)
        
        if is_buy:
            self.portfolio.buy(isin, date, price, qty, fees=fees)
        else:
            sell_results = self.portfolio.sell(isin, date, price, qty, fees=fees)
            # Deduct Taxes immediately from cash to reflect realistic NAV
            tax_due = self.tax_man.process_realized_gains(date, sell_results['stcg_base'], sell_results['ltcg_base'])
            self.portfolio.cash -= tax_due

    def _sell_all(self, isin: str, date: pd.Timestamp, prices: Dict[str, float]):
        """Helper to fully exit a position."""
        price = prices.get(isin)
        if not price: return
        total_qty = sum(lot.remaining_qty for lot in self.portfolio.holdings.get(isin, []))
        if total_qty > 0:
            self._execute_trade(isin, date, price, total_qty, is_buy=False)

    def _accrue_interest(self, date: pd.Timestamp):
        """Calculates and adds daily interest on cash balance."""
        if self.portfolio.cash <= 0: return
        
        # 5% p.a. / 365
        daily_rate = self.cash_yield_rate / 365.25
        interest = self.portfolio.cash * daily_rate
        tax = interest * self.cash_tax_rate
        net_interest = interest - tax
        
        self.portfolio.cash += net_interest
        # Optional: track in history if needed, but for now just update cash
