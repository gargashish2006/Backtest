import pandas as pd
import numpy as np

def calculate_metrics(nav_df: pd.DataFrame):
    """Calculates key performance metrics from NAV history."""
    if nav_df.empty: return {}

    # 1. Absolute Return
    initial_nav = nav_df.iloc[0]['nav']
    final_nav = nav_df.iloc[-1]['nav']
    abs_return = (final_nav / initial_nav) - 1

    # 2. CAGR
    start_date = nav_df.iloc[0]['date']
    end_date = nav_df.iloc[-1]['date']
    years = (end_date - start_date).days / 365.25
    cagr = (final_nav / initial_nav)**(1/years) - 1 if years > 0 else 0

    # 3. Drawdown
    nav_series = nav_df['nav']
    peak = nav_series.cummax()
    drawdown = (nav_series - peak) / peak
    max_drawdown = drawdown.min()

    # 4. Sharpe Ratio (Daily)
    # Assume 0 risk free rate for simplicity or use 6% govt bond rate
    daily_returns = nav_series.pct_change().dropna()
    rf_daily = (1.06)**(1/252) - 1
    excess_returns = daily_returns - rf_daily
    sharpe = (excess_returns.mean() / excess_returns.std()) * (252**0.5) if excess_returns.std() != 0 else 0

    return {
        'Absolute Return': f"{abs_return*100:.2f}%",
        'CAGR': f"{cagr*100:.2f}%",
        'Max Drawdown': f"{max_drawdown*100:.2f}%",
        'Sharpe Ratio': f"{sharpe:.2f}"
    }
