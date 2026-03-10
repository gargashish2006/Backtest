#!/usr/bin/env python
"""
Diagnostic: Identifying Max Single-Stock Loss
Hierarchical Champion (PB) vs Promoter Optimized (Baseline)
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
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from strategies.industry_group.hierarchical_champion import HierarchicalChampion
from strategies.new_research.promoter_skin_in_game_optimized import PromoterSkinInGameOptimized

def get_max_loss_for_strat(strategy_instance, name, use_pb=False):
    dates = pd.date_range('2017-05-01', '2025-11-15', freq='QS-FEB')
    portfolio = {}
    trade_returns = []
    
    print(f"\nAnalyzing {name}...")
    
    for i, date in enumerate(dates):
        if i > 0:
            # Check for exits (PB or End of Quarter)
            current_period_dates = pd.date_range(prev_date + pd.Timedelta(days=1), date)
            
            # Simulated exit check
            for isin, h in portfolio.items():
                final_p = strategy_instance.get_price(isin, date)
                if not final_p: continue
                
                # Check for intra-period PB if requested
                exited_early = False
                if use_pb:
                    for day in current_period_dates:
                        p_day = strategy_instance.get_price(isin, day)
                        if p_day and p_day >= 2.0 * h['entry_price']:
                            # PB Hit
                            trade_returns.append({
                                'isin': isin,
                                'entry_date': prev_date,
                                'exit_date': day,
                                'ret': 100.0, # Profit booked at exactly 100%
                                'type': 'PB'
                            })
                            exited_early = True
                            break
                        elif p_day and p_day <= 0.7 * h['entry_price']:
                            # SL Hit
                            trade_returns.append({
                                'isin': isin,
                                'entry_date': prev_date,
                                'exit_date': day,
                                'ret': -30.0, # Stopped out at roughly 30%
                                'type': 'SL'
                            })
                            exited_early = True
                            break
                
                if not exited_early:
                    # Regular exit at end of quarter
                    ret = (final_p / h['entry_price'] - 1) * 100
                    trade_returns.append({
                        'isin': isin,
                        'entry_date': prev_date,
                        'exit_date': date,
                        'ret': ret,
                        'type': 'Quarterly'
                    })
        
        # New selection
        stocks = strategy_instance.calculate_selection(date)
        portfolio = {}
        for isin in stocks:
            p = strategy_instance.get_price(isin, date)
            if p:
                portfolio[isin] = {'entry_price': p}
        
        prev_date = date

    df = pd.DataFrame(trade_returns)
    max_loss_row = df.sort_values('ret').iloc[0]
    
    # Get company name
    try:
        industry_df = pd.read_parquet(Path(strategy_instance.database_path) / 'industry_info.parquet')
        company = industry_df[industry_df['isin'] == max_loss_row['isin']]['company_name'].values[0]
    except:
        company = "Unknown"
        
    print(f"Max Loss: {max_loss_row['ret']:.2f}% in {company} ({max_loss_row['isin']})")
    print(f"Period: {max_loss_row['entry_date'].date()} to {max_loss_row['exit_date'].date()}")
    
    return max_loss_row, company

if __name__ == "__main__":
    h_strat = HierarchicalChampion()
    p_strat = PromoterSkinInGameOptimized()
    
    h_loss, h_comp = get_max_loss_for_strat(h_strat, "Hierarchical Champion (with PB+SL)", use_pb=True)
    p_loss, p_comp = get_max_loss_for_strat(p_strat, "Promoter Optimized (with PB+SL)", use_pb=True)
    
    print("\n" + "="*80)
    print("MAX SINGLE STOCK LOSS COMPARISON")
    print("="*80)
    print(f"{'Strategy':<35} | {'Max Loss':<10} | {'Stock':<20}")
    print("-" * 80)
    print(f"{'Hierarchical Champion (PB)':<35} | {h_loss['ret']:8.2f}% | {h_comp}")
    print(f"{'Promoter Optimized (Baseline)':<35} | {p_loss['ret']:8.2f}% | {p_comp}")
    print("="*80)
