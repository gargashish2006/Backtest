#!/usr/bin/env python
"""
Diagnostic Script: Investigating Outliers in Promoter Optimized Strategy
Focus: 2023-2025 period
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

import sys
import os
from pathlib import Path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from strategies.new_research.promoter_skin_in_game_optimized import PromoterSkinInGameOptimized

class OutlierInvestigator(PromoterSkinInGameOptimized):
    def run_diagnostic(self):
        # We focus on the period where the user saw 4x growth
        # 2023 start to 2025 start
        dates = pd.date_range('2017-05-01', '2025-11-15', freq='QS-FEB')
        
        portfolio = {}
        cash = self.INITIAL_CAPITAL
        equity = []
        trade_logs = []
        prev_date = dates[0]
        
        print(f"{'Date':<12} | {'Equity':<15} | {'Quarterly Ret':<12} | {'Top Contributor'}")
        print("-" * 80)
        
        for i, date in enumerate(dates):
            if i > 0:
                interest = cash * (self.INTEREST_RATE * (date - prev_date).days / 365.25) * (1 - self.TAX_RATE)
                cash += interest
            
            # Calculate current value of holdings
            p_val = 0
            holding_details = []
            for isin, h in portfolio.items():
                curr_p = self.get_price(isin, date)
                if curr_p:
                    stock_val = h['shares'] * curr_p
                    p_val += stock_val
                    # Record performance of this stock in the quarter
                    q_ret = (curr_p / h['entry_price'] - 1) * 100
                    h_contrib = (stock_val - (h['shares'] * h['entry_price'])) / (cash + p_val if (cash + p_val) > 0 else 1) * 100
                    holding_details.append({
                        'date': date,
                        'isin': isin,
                        'q_ret': q_ret,
                        'val': stock_val,
                        'contrib': h_contrib
                    })
            
            curr_val = cash + p_val
            q_return_pct = 0
            if i > 0 and equity:
                q_return_pct = (curr_val / equity[-1]['value'] - 1) * 100
            
            # Sort holdings by contribution
            top_stock = "N/A"
            if holding_details:
                top_h = sorted(holding_details, key=lambda x: x['contrib'], reverse=True)[0]
                top_stock = f"{top_h['isin']} ({top_h['q_ret']:.1f}%)"
                trade_logs.extend(holding_details)

            print(f"{str(date.date()):<12} | ₹{curr_val:14,.0f} | {q_return_pct:12.2f}% | {top_stock}")
            
            # Rebalance
            stocks = self.calculate_selection(date)
            if not stocks:
                equity.append({'date': date, 'value': curr_val})
                portfolio = {}
                prev_date = date
                continue
            
            target_per_stock = curr_val * min(0.95/len(stocks), self.MAX_WEIGHT)
            cash = curr_val
            portfolio = {}
            for isin in stocks:
                p = self.get_price(isin, date)
                if p:
                    s = int(target_per_stock / (p * 1.002))
                    if s > 0:
                        portfolio[isin] = {'shares': s, 'entry_price': p}
                        cash -= s * p * 1.002
            
            equity.append({'date': date, 'value': curr_val})
            prev_date = date

        # Final Analysis
        log_df = pd.DataFrame(trade_logs)
        print("\n" + "="*80)
        print("TOP 10 INDIVIDUAL QUARTERLY RETURNS (OUTLIER CHECK)")
        print("="*80)
        top_os = log_df.sort_values('q_ret', ascending=False).head(10)
        print(top_os[['date', 'isin', 'q_ret', 'contrib']].to_string(index=False))
        
        print("\n" + "="*80)
        print("ANALYSIS OF 2023-2025 SPURT")
        print("="*80)
        spurt = log_df[(log_df['date'] >= '2023-01-01') & (log_df['date'] <= '2025-01-31')]
        if not spurt.empty:
            avg_ret = spurt['q_ret'].mean()
            median_ret = spurt['q_ret'].median()
            max_ret = spurt['q_ret'].max()
            print(f"Average Quarterly Stock Return: {avg_ret:.2f}%")
            print(f"Median Quarterly Stock Return: {median_ret:.2f}%")
            print(f"Max Single Stock Quarterly Return: {max_ret:.2f}%")
            
            outliers = spurt[spurt['q_ret'] > 100]
            if not outliers.empty:
                print(f"\nMulti-baggers in single quarters (>100%):")
                print(outliers[['date', 'isin', 'q_ret']].to_string(index=False))
            else:
                print("\nNo single-stock >100% returns found in the spurt period.")

if __name__ == "__main__":
    investigator = OutlierInvestigator()
    investigator.run_diagnostic()
