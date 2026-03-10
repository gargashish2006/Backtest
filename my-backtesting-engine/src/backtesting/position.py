"""
Position management and tracking
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """Represents a single position in a stock"""
    
    # Identification
    isin: str
    symbol: str
    exchange: str
    
    # Entry details
    entry_date: datetime
    entry_price: float
    quantity: int
    
    # Costs
    entry_transaction_cost: float
    entry_impact_cost: float
    
    # Current state
    current_price: float = 0.0
    current_date: Optional[datetime] = None
    
    # Exit details (filled when position is closed)
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_transaction_cost: float = 0.0
    exit_impact_cost: float = 0.0
    
    # Tax details
    tax_paid: float = 0.0
    holding_days: int = 0
    is_long_term: bool = False
    
    # P&L
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    def __post_init__(self):
        """Calculate initial investment"""
        self.investment = self.quantity * self.entry_price
        self.total_entry_cost = self.entry_transaction_cost + self.entry_impact_cost
        self.current_price = self.entry_price
        self.current_date = self.entry_date
    
    @property
    def is_open(self) -> bool:
        """Check if position is still open"""
        return self.exit_date is None
    
    @property
    def market_value(self) -> float:
        """Current market value of position"""
        return self.quantity * self.current_price
    
    def update_current_price(self, price: float, date: datetime):
        """Update current price and unrealized P&L"""
        self.current_price = price
        self.current_date = date
        
        if self.is_open:
            # Calculate unrealized P&L (no exit costs yet)
            self.unrealized_pnl = (self.market_value - self.investment - 
                                  self.total_entry_cost)
    
    def close_position(self, exit_price: float, exit_date: datetime, 
                       transaction_cost: float, impact_cost: float, 
                       tax_rate: float) -> dict:
        """
        Close the position and calculate final P&L with all costs
        
        Returns:
            dict with closure details
        """
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_transaction_cost = transaction_cost
        self.exit_impact_cost = impact_cost
        
        # Calculate holding period
        self.holding_days = (exit_date - self.entry_date).days
        self.is_long_term = self.holding_days >= 365
        
        # Calculate gross P&L
        gross_pnl = (exit_price - self.entry_price) * self.quantity
        
        # Subtract all costs
        total_costs = (self.entry_transaction_cost + 
                      self.entry_impact_cost + 
                      self.exit_transaction_cost + 
                      self.exit_impact_cost)
        
        pnl_before_tax = gross_pnl - total_costs
        
        # Calculate tax (only on profits)
        if pnl_before_tax > 0:
            self.tax_paid = pnl_before_tax * tax_rate
        else:
            self.tax_paid = 0.0
        
        # Final realized P&L
        self.realized_pnl = pnl_before_tax - self.tax_paid
        self.unrealized_pnl = 0.0
        
        return {
            'isin': self.isin,
            'symbol': self.symbol,
            'entry_date': self.entry_date,
            'exit_date': self.exit_date,
            'holding_days': self.holding_days,
            'is_long_term': self.is_long_term,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'investment': self.investment,
            'gross_pnl': gross_pnl,
            'total_costs': total_costs,
            'pnl_before_tax': pnl_before_tax,
            'tax_paid': self.tax_paid,
            'realized_pnl': self.realized_pnl,
            'return_pct': (self.realized_pnl / self.investment * 100) if self.investment > 0 else 0
        }
    
    def to_dict(self) -> dict:
        """Convert position to dictionary"""
        return {
            'isin': self.isin,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'entry_date': self.entry_date,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'investment': self.investment,
            'current_price': self.current_price,
            'current_date': self.current_date,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'is_open': self.is_open,
            'exit_date': self.exit_date,
            'exit_price': self.exit_price,
            'holding_days': self.holding_days,
            'is_long_term': self.is_long_term,
            'realized_pnl': self.realized_pnl,
            'tax_paid': self.tax_paid
        }
