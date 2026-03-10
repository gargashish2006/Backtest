import pandas as pd
from typing import Dict

class FeeModel:
    """Calculates transaction and impact costs for trades."""
    def __init__(self, transaction_fee_rate: float = 0.0015, impact_cost_rate: float = 0.005):
        # Default: 0.15% (Brokerage + GST + STT) + 0.50% Slippage
        self.transaction_fee_rate = transaction_fee_rate
        self.impact_cost_rate = impact_cost_rate
        self.total_fees = 0.0

    def calculate_costs(self, order_value: float, is_buy: bool) -> float:
        """Returns total cost (fees + impact) for an order."""
        t_costs = order_value * self.transaction_fee_rate
        i_costs = order_value * self.impact_cost_rate
        total = t_costs + i_costs
        self.total_fees += total
        return total

class TaxManager:
    """Manages capital gains taxes and exemptions."""
    def __init__(self, stcg_rate: float = 0.20, ltcg_rate: float = 0.125, ltcg_exemption: float = 125000):
        self.stcg_rate = stcg_rate
        self.ltcg_rate = ltcg_rate
        self.ltcg_exemption = ltcg_exemption
        self.total_realized_stcg = 0.0
        self.total_realized_ltcg = 0.0
        self.tax_paid_history = []

    def process_realized_gains(self, date: pd.Timestamp, stcg_base: float, ltcg_base: float) -> float:
        """Calculates tax liability for realized gains and updates history."""
        # Note: In real world, taxes are paid at end of FY. 
        # Here we can track liability or deduct immediately. 
        # Deduction immediately is better for conservative NAV tracking.
        
        stcg_tax = max(0, stcg_base * self.stcg_rate)
        # Simplified LTCG: Just applies rate (ignoring slab for now unless we track fiscal year)
        ltcg_tax = max(0, ltcg_base * self.ltcg_rate)
        
        total_tax = stcg_tax + ltcg_tax
        self.total_realized_stcg += stcg_base
        self.total_realized_ltcg += ltcg_base
        
        self.tax_paid_history.append({
            'date': date,
            'stcg_tax': stcg_tax,
            'ltcg_tax': ltcg_tax,
            'total_tax': total_tax
        })
        return total_tax
