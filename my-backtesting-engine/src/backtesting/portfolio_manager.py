"""
Portfolio management with position tracking and capital allocation
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .config import BacktestConfig
from .position import Position


@dataclass
class PortfolioState:
    """Snapshot of portfolio state at a point in time"""
    
    date: datetime
    total_capital: float
    cash: float
    invested_value: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    num_positions: int
    total_tax_paid: float
    total_costs_paid: float
    return_pct: float


class Portfolio:
    """
    Manages portfolio positions, capital allocation, and P&L tracking
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        
        # Capital management
        self.initial_capital = config.INITIAL_CAPITAL
        self.cash = config.INITIAL_CAPITAL
        self.total_capital = config.INITIAL_CAPITAL
        
        # Positions
        self.open_positions: Dict[str, Position] = {}  # isin -> Position
        self.closed_positions: List[Position] = []
        
        # Tracking
        self.total_tax_paid = 0.0
        self.total_costs_paid = 0.0
        self.total_realized_pnl = 0.0
        self.total_unrealized_pnl = 0.0
        
        # History
        self.history: List[PortfolioState] = []
        
        # Trade log
        self.trade_log: List[dict] = []
    
    @property
    def num_open_positions(self) -> int:
        """Number of currently open positions"""
        return len(self.open_positions)
    
    @property
    def invested_value(self) -> float:
        """Total invested value (cost basis) of open positions"""
        return sum(pos.investment + pos.total_entry_cost 
                  for pos in self.open_positions.values())
    
    @property
    def market_value(self) -> float:
        """Current market value of all open positions"""
        return sum(pos.market_value for pos in self.open_positions.values())
    
    @property
    def can_open_new_position(self) -> bool:
        """Check if we can open a new position"""
        return self.num_open_positions < self.config.MAX_POSITIONS
    
    @property
    def capital_per_position(self) -> float:
        """Capital to allocate per position"""
        return self.config.capital_per_position()
    
    def calculate_position_size(self, price: float) -> int:
        """
        Calculate number of shares to buy given a price
        
        Args:
            price: Current price per share
            
        Returns:
            Number of shares (quantity)
        """
        # Available capital for this position
        available = self.capital_per_position
        
        # Account for entry costs
        cost_multiplier = 1 + self.config.costs.total_buy_cost()
        
        # Calculate affordable quantity
        quantity = int(available / (price * cost_multiplier))
        
        return max(1, quantity)  # At least 1 share
    
    def open_position(self, isin: str, symbol: str, exchange: str,
                     price: float, date: datetime) -> Optional[Position]:
        """
        Open a new position
        
        Args:
            isin: Stock ISIN
            symbol: Stock symbol
            exchange: Exchange (NSE/BSE)
            price: Entry price
            date: Entry date
            
        Returns:
            Position object if successful, None otherwise
        """
        # Check if we can open new position
        if not self.can_open_new_position:
            return None
        
        # Check if position already exists
        if isin in self.open_positions:
            return None
        
        # Calculate position size
        quantity = self.calculate_position_size(price)
        
        # Calculate costs
        investment = quantity * price
        transaction_cost = investment * self.config.costs.TRANSACTION_COST_BUY
        impact_cost = investment * self.config.costs.IMPACT_COST_BUY
        
        total_cost = investment + transaction_cost + impact_cost
        
        # Check if we have enough cash
        if total_cost > self.cash:
            return None
        
        # Create position
        position = Position(
            isin=isin,
            symbol=symbol,
            exchange=exchange,
            entry_date=date,
            entry_price=price,
            quantity=quantity,
            entry_transaction_cost=transaction_cost,
            entry_impact_cost=impact_cost
        )
        
        # Update cash
        self.cash -= total_cost
        self.total_costs_paid += (transaction_cost + impact_cost)
        
        # Add to open positions
        self.open_positions[isin] = position
        
        # Log trade
        self.trade_log.append({
            'date': date,
            'action': 'BUY',
            'isin': isin,
            'symbol': symbol,
            'price': price,
            'quantity': quantity,
            'investment': investment,
            'transaction_cost': transaction_cost,
            'impact_cost': impact_cost,
            'total_cost': total_cost
        })
        
        return position
    
    def close_position(self, isin: str, price: float, date: datetime) -> Optional[dict]:
        """
        Close an existing position
        
        Args:
            isin: Stock ISIN
            price: Exit price
            date: Exit date
            
        Returns:
            Dictionary with closure details, None if position doesn't exist
        """
        if isin not in self.open_positions:
            return None
        
        position = self.open_positions[isin]
        
        # Calculate exit costs
        proceeds = position.quantity * price
        transaction_cost = proceeds * self.config.costs.TRANSACTION_COST_SELL
        impact_cost = proceeds * self.config.costs.IMPACT_COST_SELL
        
        # Determine tax rate based on holding period
        holding_days = (date - position.entry_date).days
        tax_rate = self.config.costs.get_tax_rate(holding_days)
        
        # Close position
        closure_details = position.close_position(
            exit_price=price,
            exit_date=date,
            transaction_cost=transaction_cost,
            impact_cost=impact_cost,
            tax_rate=tax_rate
        )
        
        # Update portfolio
        net_proceeds = proceeds - transaction_cost - impact_cost - position.tax_paid
        self.cash += net_proceeds
        
        # Update totals
        self.total_costs_paid += (transaction_cost + impact_cost)
        self.total_tax_paid += position.tax_paid
        self.total_realized_pnl += position.realized_pnl
        
        # Move to closed positions
        self.closed_positions.append(position)
        del self.open_positions[isin]
        
        # Update total capital
        self.total_capital = self.cash + self.market_value
        
        # Log trade
        self.trade_log.append({
            'date': date,
            'action': 'SELL',
            'isin': isin,
            'symbol': position.symbol,
            'price': price,
            'quantity': position.quantity,
            'proceeds': proceeds,
            'transaction_cost': transaction_cost,
            'impact_cost': impact_cost,
            'tax_paid': position.tax_paid,
            'realized_pnl': position.realized_pnl,
            'holding_days': holding_days,
            'is_long_term': position.is_long_term
        })
        
        return closure_details
    
    def update_positions(self, prices: Dict[str, float], date: datetime):
        """
        Update current prices for all open positions
        
        Args:
            prices: Dictionary of isin -> current_price
            date: Current date
        """
        self.total_unrealized_pnl = 0.0
        
        for isin, position in self.open_positions.items():
            if isin in prices:
                position.update_current_price(prices[isin], date)
                self.total_unrealized_pnl += position.unrealized_pnl
        
        # Update total capital
        self.total_capital = self.cash + self.market_value
    
    def record_state(self, date: datetime):
        """Record current portfolio state"""
        total_pnl = self.total_realized_pnl + self.total_unrealized_pnl
        return_pct = ((self.total_capital - self.initial_capital) / 
                     self.initial_capital * 100)
        
        state = PortfolioState(
            date=date,
            total_capital=self.total_capital,
            cash=self.cash,
            invested_value=self.invested_value,
            market_value=self.market_value,
            unrealized_pnl=self.total_unrealized_pnl,
            realized_pnl=self.total_realized_pnl,
            total_pnl=total_pnl,
            num_positions=self.num_open_positions,
            total_tax_paid=self.total_tax_paid,
            total_costs_paid=self.total_costs_paid,
            return_pct=return_pct
        )
        
        self.history.append(state)
        return state
    
    def get_summary(self) -> dict:
        """Get portfolio performance summary"""
        total_trades = len(self.closed_positions)
        winning_trades = sum(1 for pos in self.closed_positions if pos.realized_pnl > 0)
        losing_trades = sum(1 for pos in self.closed_positions if pos.realized_pnl < 0)
        
        wins = [pos.realized_pnl for pos in self.closed_positions if pos.realized_pnl > 0]
        losses = [pos.realized_pnl for pos in self.closed_positions if pos.realized_pnl < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.total_capital,
            'total_return': self.total_capital - self.initial_capital,
            'total_return_pct': ((self.total_capital - self.initial_capital) / 
                                self.initial_capital * 100),
            'total_realized_pnl': self.total_realized_pnl,
            'total_unrealized_pnl': self.total_unrealized_pnl,
            'total_tax_paid': self.total_tax_paid,
            'total_costs_paid': self.total_costs_paid,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'open_positions': self.num_open_positions,
            'cash': self.cash,
            'invested_value': self.invested_value,
            'market_value': self.market_value
        }
