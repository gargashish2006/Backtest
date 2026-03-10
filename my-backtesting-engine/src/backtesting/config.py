"""
Backtesting configuration and constants
"""

from dataclasses import dataclass


@dataclass
class TradingCosts:
    """Trading costs and tax rates"""
    
    # Transaction costs (as percentage)
    TRANSACTION_COST_BUY: float = 0.0003  # 0.03% - STT, brokerage, etc.
    TRANSACTION_COST_SELL: float = 0.0003  # 0.03%
    
    # Impact costs (as percentage) - market impact
    IMPACT_COST_BUY: float = 0.0005  # 0.05%
    IMPACT_COST_SELL: float = 0.0005  # 0.05%
    
    # Tax rates (as percentage of profit)
    SHORT_TERM_TAX_RATE: float = 0.20  # 20% for holding < 1 year (Equity)
    LONG_TERM_TAX_RATE: float = 0.125  # 12.5% for holding >= 1 year (Equity)
    LONG_TERM_TAX_EXEMPTION: float = 125000  # ₹1.25L exempt (per year)
    
    def total_buy_cost(self) -> float:
        """Total cost percentage for buy side"""
        return self.TRANSACTION_COST_BUY + self.IMPACT_COST_BUY
    
    def total_sell_cost(self) -> float:
        """Total cost percentage for sell side"""
        return self.TRANSACTION_COST_SELL + self.IMPACT_COST_SELL
    
    def get_tax_rate(self, holding_days: int) -> float:
        """Get applicable tax rate based on holding period"""
        if holding_days < 365:
            return self.SHORT_TERM_TAX_RATE
        else:
            return self.LONG_TERM_TAX_RATE


@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    
    # Capital management
    INITIAL_CAPITAL: float = 100000  # ₹1 Lakh
    MAX_POSITIONS: int = 10  # Maximum concurrent positions
    
    # Position sizing
    POSITION_SIZING: str = "equal_weight"  # equal_weight | risk_based | kelly
    
    # Trading costs
    costs: TradingCosts = None
    
    def __post_init__(self):
        if self.costs is None:
            self.costs = TradingCosts()
    
    def capital_per_position(self) -> float:
        """Capital allocated per position"""
        return self.INITIAL_CAPITAL / self.MAX_POSITIONS
    
    def update_max_positions(self, max_pos: int):
        """Update maximum positions"""
        self.MAX_POSITIONS = max_pos


# Default configurations for different strategy types
CONSERVATIVE_CONFIG = BacktestConfig(
    INITIAL_CAPITAL=100000,
    MAX_POSITIONS=10,
    POSITION_SIZING="equal_weight"
)

MODERATE_CONFIG = BacktestConfig(
    INITIAL_CAPITAL=100000,
    MAX_POSITIONS=20,
    POSITION_SIZING="equal_weight"
)

AGGRESSIVE_CONFIG = BacktestConfig(
    INITIAL_CAPITAL=100000,
    MAX_POSITIONS=50,
    POSITION_SIZING="equal_weight"
)
