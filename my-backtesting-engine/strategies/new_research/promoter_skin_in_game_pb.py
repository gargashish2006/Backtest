#!/usr/bin/env python
"""
Promoter Skin-in-the-Game Strategy (OPTIMIZED)
** WITH 100% PROFIT BOOKING **

Logic:
1. Rebalance every Quarter.
2. Intra-quarter: If any stock hits 2x its entry price, sell it immediately.
3. Move proceeds to cash (earning interest) until next rebalance.
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.new_research.promoter_skin_in_game_optimized import PromoterSkinInGameOptimized

class PromoterSkinInGameProfitBooking(PromoterSkinInGameOptimized):
    def __init__(self):
        super().__init__()
        print("+" * 100)
        print("ADDING 100% PROFIT BOOKING RULE")
        print("+" * 100)

    def run(self):
        dates = pd.date_range('2017-05-01', '2025-11-15', freq='QS-FEB')
        portfolio = {}; cash = self.INITIAL_CAPITAL; equity = []; prev_date = dates[0]
        
        print(f"Starting PROMOTER Backtest with 100% PROFIT BOOKING...")
        
        for i, date in enumerate(dates):
            if i > 0:
                # 1. PROCESS INTRA-QUARTER PROFIT BOOKING
                current_period_dates = pd.date_range(prev_date + pd.Timedelta(days=1), date)
                
                for day in current_period_dates:
                    to_liquidate = []
                    for isin, h in portfolio.items():
                        if h.get('booked', False): continue
                        
                        price = self.get_price(isin, day)
                        if price:
                            if price >= 2.0 * h['entry_price']:
                                # PROFIT BOOKED!
                                exit_val = h['shares'] * price * (1 - 0.002) 
                                h['booked'] = True
                                h['exit_reason'] = 'PB'
                                h['exit_date'] = day
                                h['exit_value'] = exit_val
                                to_liquidate.append(isin)
                            elif price <= 0.7 * h['entry_price']:
                                # STOP LOSS HIT!
                                exit_val = h['shares'] * price * (1 - 0.002) 
                                h['booked'] = True
                                h['exit_reason'] = 'SL'
                                h['exit_date'] = day
                                h['exit_value'] = exit_val
                                to_liquidate.append(isin)
                    
                    for isin in to_liquidate:
                        h_exit = portfolio[isin]
                        days_remaining = (date - day).days
                        if days_remaining > 0:
                            interest = h_exit['exit_value'] * (self.INTEREST_RATE * days_remaining / 365.25) * (1 - self.TAX_RATE)
                            cash += h_exit['exit_value'] + interest
                        else:
                            cash += h_exit['exit_value']
                
                main_interest = cash_at_start * (self.INTEREST_RATE * (date - prev_date).days / 365.25) * (1 - self.TAX_RATE)
                cash += main_interest
            
            # 2. CALCULATE CURRENT VALUE
            p_val = sum([h['shares'] * (self.get_price(isin, date) or 0) for isin, h in portfolio.items() if not h.get('booked', False)])
            curr_val = cash + p_val
            
            # 3. REBALANCE
            stocks = self.calculate_selection(date)
            
            portfolio_count = len(stocks)
            cash_at_start = 0 
            
            if portfolio_count == 0:
                cash = curr_val; portfolio = {}
                cash_at_start = cash
            else:
                target_per_stock = curr_val * min(0.95/len(stocks), self.MAX_WEIGHT)
                cash = curr_val; portfolio = {}
                for isin in stocks:
                    p = self.get_price(isin, date)
                    if p:
                        s = int(target_per_stock / (p * 1.002))
                        if s > 0:
                            portfolio[isin] = {'shares': s, 'entry_price': p, 'booked': False}
                            cash -= s * p * 1.002
                cash_at_start = cash
            
            invested = sum([h['shares'] * (self.get_price(k, date) or 0) for k, h in portfolio.items() if not h.get('booked', False)])
            val = cash + invested
            equity.append({'date': date, 'value': val})
            print(f"[{date.date()}] Value: ₹{val:,.0f} | Ratio: {invested/val:.1%} | Stocks: {len([x for x in portfolio if not portfolio[x]['booked']])}")
            prev_date = date

        res = pd.DataFrame(equity)
        ret = (res.iloc[-1]['value']/res.iloc[0]['value'] - 1) * 100
        print(f"\nPROMOTER (PROFIT BOOKING) RETURN: {ret:.2f}%")
        p = self.base_path / 'strategies' / 'new_research' / 'outputs'
        p.mkdir(parents=True, exist_ok=True)
        res.to_csv(p / f'promoter_skin_in_game_pb_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', index=False)

if __name__ == "__main__":
    PromoterSkinInGameProfitBooking().run()
