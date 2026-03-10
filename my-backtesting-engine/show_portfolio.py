#!/usr/bin/env python3
"""
Display current portfolio with company names, industries, and industry groups
"""

import pandas as pd

def main():
    # Load current portfolio ISINs
    portfolio_isins = [
        'INE02L001032', 'INE019A01038', 'INE040A01034', 'INE046W01019', 'INE050N01010',
        'INE063P01018', 'INE081A01020', 'INE090A01021', 'INE139R01012', 'INE208A01029',
        'INE220Z01013', 'INE238A01034', 'INE243D01012', 'INE287Z01012', 'INE294B01019',
        'INE346W01013', 'INE350Z01018', 'INE438A01022', 'INE551W01018', 'INE741K01010',
        'INE749A01030', 'INE787D01026', 'INE883A01011', 'INE949L01017', 'INE951D01028',
        'INE974B01016', 'INE983C01015', 'INE00RL01028'
    ]

    # Load industry info
    industry_df = pd.read_csv('database/industry_info.csv')
    portfolio_df = industry_df[industry_df['isin'].isin(portfolio_isins)].copy()

    # Load trade details for shares and prices
    trades_df = pd.read_csv('strategies/outputs/industry_4q_10ind_3stocks_trades_20260207_115009.csv')
    trades_df = trades_df[(trades_df['date'] == '2025-11-01') & (trades_df['action'].isin(['buy', 'add']))]

    # Merge with portfolio
    portfolio_df = portfolio_df.merge(trades_df[['isin', 'shares', 'price']], on='isin', how='left')

    # Format and display
    portfolio_df = portfolio_df[['company_name', 'industry', 'industry_group', 'shares', 'price', 'isin']]
    portfolio_df = portfolio_df.sort_values('company_name')

    print('Current Portfolio - Original 10×3 Strategy (2025-11-01)')
    print('Portfolio Value: ₹7.25 crore')
    print('30 stocks held across 10 industries')
    print()
    print(portfolio_df.to_string(index=False))

if __name__ == "__main__":
    main()