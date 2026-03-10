import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional

class TaxLot:
    """Represents a single purchase of a security for FIFO accounting."""
    def __init__(self, buy_date: datetime, buy_price: float, qty: int):
        self.buy_date = pd.to_datetime(buy_date)
        self.buy_price = float(buy_price)
        self.qty = int(qty)
        self.remaining_qty = int(qty)

    def is_ltcg(self, sell_date: datetime) -> bool:
        """Determines if the lot qualifies for Long-Term Capital Gains (> 365 days)."""
        return (pd.to_datetime(sell_date) - self.buy_date).days >= 365

    def __repr__(self):
        return f"TaxLot(date={self.buy_date.date()}, price={self.buy_price:.2f}, qty={self.remaining_qty})"

class Portfolio:
    """Handles daily positions, cash management, and trade execution."""
    def __init__(self, initial_cash: float):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.holdings: Dict[str, List[TaxLot]] = {} # isin -> list of lots
        self.nav_history: List[Dict] = []
        self.trade_log: List[Dict] = []
        self.last_prices: Dict[str, float] = {}
        
    def buy(self, isin: str, date: datetime, price: float, qty: int, fees: float = 0.0):
        """Executes a buy order and creates a new TaxLot."""
        total_cost = (price * qty) + fees
        if total_cash_required := total_cost > self.cash:
            # Optional: Implement protective rounding or erroring
            qty = int(self.cash / (price * 1.002)) # Simple fallback
            total_cost = (price * qty) + fees
            
        if qty <= 0: return

        self.cash -= total_cost
        if isin not in self.holdings:
            self.holdings[isin] = []
        
        self.holdings[isin].append(TaxLot(date, price, qty))
        self.trade_log.append({
            'date': date, 'isin': isin, 'type': 'BUY', 
            'price': price, 'qty': qty, 'fees': fees, 'net_value': total_cost,
            'realized_gain': 0
        })

    def sell(self, isin: str, date: datetime, price: float, qty: int, fees: float = 0.0) -> Dict:
        """Executes a sell order using FIFO and returns gain/tax details."""
        if isin not in self.holdings or not self.holdings[isin]:
            return {'realized_gain': 0, 'stcg_base': 0, 'ltcg_base': 0, 'qty_sold': 0}

        lots = self.holdings[isin]
        qty_to_sell = qty
        total_realized_gain = 0
        total_stcg_base = 0
        total_ltcg_base = 0
        actual_qty_sold = 0

        while qty_to_sell > 0 and lots:
            lot = lots[0]
            sell_from_lot = min(qty_to_sell, lot.remaining_qty)
            
            # Gain calculation (Slippage/Fees should be handled by FeeModel externally or passed here)
            # Net proceeds = (price * sold) - fees_pro_rata
            # Cost basis = (lot.buy_price * sold)
            lot_gain = (price * sell_from_lot) - (lot.buy_price * sell_from_lot)
            
            if lot.is_ltcg(date):
                total_ltcg_base += lot_gain
            else:
                total_stcg_base += lot_gain
            
            total_realized_gain += lot_gain
            actual_qty_sold += sell_from_lot
            lot.remaining_qty -= sell_from_lot
            qty_to_sell -= sell_from_lot
            
            if lot.remaining_qty == 0:
                lots.pop(0)

        self.cash += (price * actual_qty_sold) - fees
        self.trade_log.append({
            'date': date, 'isin': isin, 'type': 'SELL',
            'price': price, 'qty': actual_qty_sold, 'fees': fees, 'net_value': (price * actual_qty_sold) - fees,
            'realized_gain': total_realized_gain
        })
        
        # Cleanup if no lots remain
        if not self.holdings[isin]:
            del self.holdings[isin]
            
        return {
            'realized_gain': total_realized_gain,
            'stcg_base': total_stcg_base,
            'ltcg_base': total_ltcg_base,
            'qty_sold': actual_qty_sold
        }

    def get_market_value(self, price_lookup: Dict[str, float]) -> float:
        """Calculates total value of all holdings based on provided prices. Falls back to last seen price."""
        mv = 0.0
        for isin, lots in self.holdings.items():
            curr_price = price_lookup.get(isin)
            if curr_price is not None:
                self.last_prices[isin] = curr_price
            else:
                curr_price = self.last_prices.get(isin, 0.0)
            
            total_qty = sum(lot.remaining_qty for lot in lots)
            mv += total_qty * curr_price
        return mv

    def record_nav(self, date: datetime, price_lookup: Dict[str, float]):
        """Snapshots the daily NAV."""
        mv = self.get_market_value(price_lookup)
        self.nav_history.append({
            'date': pd.to_datetime(date),
            'cash': self.cash,
            'market_value': mv,
            'nav': self.cash + mv,
            'positions': str(list(self.holdings.keys()))
        })
