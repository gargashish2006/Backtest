import pandas as pd
from typing import Dict, List
from .momentum import MomentumStrategy

class StaggeredMomentumStrategy:
    """Manages a portfolio divided into 4 tranches, staggered quarterly."""
    def __init__(self, data_handler, num_stocks_per_tranche: int = 15):
        self.dh = data_handler
        self.base_strat = MomentumStrategy(data_handler, num_stocks=num_stocks_per_tranche)
        self.tranches: Dict[int, List[str]] = {0: [], 1: [], 2: [], 3: []}
        self.is_bootstrapped = False

    def calculate_selection(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns consolidated target weights (isin -> weight)."""
        # Determine which tranche to rebalance based on date
        # Quarter mappings: May(0), Aug(1), Nov(2), Feb(3)
        month = date.month
        tranche_idx = {5: 0, 8: 1, 11: 2, 2: 3}.get(month)
        
        if tranche_idx is None:
            # Not a rebalance month, return existing state (though engine shouldn't call)
            return self._get_weights()

        # 1. Generate new selection for the active tranche
        new_selection = self.base_strat.calculate_selection(date)
        
        if not self.is_bootstrapped:
            # FIRST REBALANCE: Seed all tranches with the same selection
            for i in range(4):
                self.tranches[i] = new_selection
            self.is_bootstrapped = True
        else:
            # Regular rebalance: only update the dedicated tranche
            if new_selection:
                self.tranches[tranche_idx] = new_selection

        return self._get_weights()

    def _get_weights(self) -> Dict[str, float]:
        """Consolidates tranches into a single weight map."""
        weights = {}
        # Each tranche is 25% of the portfolio
        # If a stock appears in multiple tranches, its weight sums up
        tranche_weight = 0.25
        
        for idx in range(4):
            stocks = self.tranches[idx]
            if not stocks: continue
            
            weight_per_stock = tranche_weight / len(stocks)
            for isin in stocks:
                weights[isin] = weights.get(isin, 0.0) + weight_per_stock
        
        return weights
