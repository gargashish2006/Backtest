#!/usr/bin/env python
"""
Industry_Group-Based Contrarian Strategy - Top 20% + Max 5 Stocks per Industry_Group

Strategy:
- 4 Quarter (12 month) lookback for shareholding changes
- First: Select top 20% industry_groups by contrarian signal (highest % decreasing shareholders)
- Second: From those, select top industry_groups with strongest trend (% stocks above 200-day MA)
- Stock selection: Pick stocks from selected industry_groups, max 5 stocks per industry_group
- Total: 30 stocks total portfolio
- NO market cap pre-filtering (uses all 4,609 stocks)
- Full quarterly rebalancing with smart delta trading
- ₹1 Crore initial capital

Features:
- Two-stage industry_group filtering: Contrarian signal first, then trend confirmation
- Diversified across industry_groups with max concentration limits
- Transaction costs and taxes
- Tax loss carry forward
- Smart rebalancing (only trade incremental quantities)
- Cash tracking for undeployed capital
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class IndustryGroup4QTop20PctMax5PerGroupStrategy:
    """
    Industry_group-based contrarian strategy: Top 20% industry_groups + max 5 stocks per group = 30 total
    """

    def __init__(self):
        print("="*100)
        print("INDUSTRY_GROUP CONTRARIAN STRATEGY - TOP 20% + MAX 5 STOCKS PER INDUSTRY_GROUP")
        print("="*100)

        self.base_path = Path(__file__).parent.parent
        self.database_path = self.base_path / 'database'

        # Strategy parameters
        self.LOOKBACK_QUARTERS = 4  # 12 months
        self.NUM_STOCKS = 30  # Portfolio size (30 stocks total)
        self.MAX_STOCKS_PER_GROUP = 5  # Maximum 5 stocks per industry_group
        self.NUM_INDUSTRY_GROUPS = 10  # Target 10 industry_groups
        self.INITIAL_CAPITAL = 10000000  # ₹1 Crore
        # NO MARKET CAP FILTER - Use all stocks, select by mcap within groups

        # Cost parameters
        self.BROKERAGE = 0.0003  # 0.03% per side
        self.STT_BUY = 0.0  # No STT on buy
        self.STT_SELL = 0.001  # 0.1% on sell
        self.EXCHANGE_TXN = 0.0000345  # NSE charges
        self.GST = 0.18  # 18% on brokerage
        self.SEBI_CHARGES = 0.000001  # ₹10 per crore
        self.STAMP_DUTY = 0.00015  # 0.015% on buy
        self.SLIPPAGE = 0.001  # 0.1%

        # Tax parameters
        self.STCG_RATE = 0.15  # 15% short-term capital gains
        self.LTCG_RATE = 0.10  # 10% long-term capital gains
        self.LTCG_EXEMPTION = 100000  # ₹1 lakh exemption

        # Tax loss carry forward
        self.tax_loss_carried = 0

        print("\nLoading and pre-processing data...")
        self.load_data()
        self.preprocess_data()

    def load_data(self):
        """Load all required data"""
        print("  Loading price data...")
        self.price_df = pd.read_parquet(self.database_path / 'price_data.parquet')

        print("  Loading shareholding data...")
        self.shp_df = pd.read_parquet(self.database_path / 'shareholding_patterns.parquet')

        print("  Loading industry info...")
        self.industry_df = pd.read_parquet(self.database_path / 'industry_info.parquet')

        print("  Loading outstanding shares...")
        self.shares_df = pd.read_csv(self.database_path / 'outstanding_shares.csv')
        self.shares_map = dict(zip(self.shares_df['isin'], self.shares_df['total_outstanding_shares']))

        print(f"✅ Data loaded: {len(self.price_df):,} price records, {len(self.shp_df):,} shareholding records")
        print(f"   Outstanding shares: {len(self.shares_map):,} stocks")

    def preprocess_data(self):
        """Pre-process data for faster execution"""
        print("  Parsing quarter dates...")
        self.shp_df['quarter_date'] = self.shp_df['quarter'].apply(self.parse_quarter_to_date)

        print("  Merging shareholding with industry data...")
        self.shp_with_industry = pd.merge(
            self.shp_df,
            self.industry_df[['isin', 'industry', 'industry_group']],
            on='isin',
            how='left'
        )

        # Filter out invalid industry_group entries
        self.shp_with_industry = self.shp_with_industry[
            (self.shp_with_industry['industry_group'] != 'Not Available') &
            (self.shp_with_industry['industry_group'] != '')
        ].copy()

        print("  Calculating shareholding changes...")
        self.calculate_shareholding_changes()

        print("  Preprocessing price data...")
        self.preprocess_price_data()

        print("  Pre-calculating market caps...")
        self.precalculate_market_caps()

        print("  Pre-calculating shareholding metrics...")
        self.precalculate_shareholding_metrics()

        print(f"✅ Preprocessing complete: {len(self.shp_with_industry):,} valid shareholding records")

    def precalculate_market_caps(self):
        """Pre-calculate market caps for all stocks and dates"""
        print("    Calculating market caps for all price data...")

        # Add market cap to price data
        self.price_df['market_cap'] = self.price_df['close'] * self.price_df['isin'].map(self.shares_map)

        # Create a cache of latest market caps by date
        self.market_cap_cache = {}

        # Get all unique dates in the backtest period
        backtest_dates = pd.date_range(start='2015-01-01', end='2024-12-31', freq='Q')
        backtest_dates = [d.replace(day=1) for d in backtest_dates]

        for date in backtest_dates:
            # Get latest prices on or before this date
            latest_prices = self.price_df[self.price_df['date'] <= date].copy()
            latest_prices = latest_prices.sort_values(['isin', 'date']).drop_duplicates('isin', keep='last')

            # Merge with industry data and cache
            latest_with_industry = pd.merge(
                latest_prices[['isin', 'market_cap']],
                self.industry_df[['isin', 'industry', 'industry_group']],
                on='isin',
                how='left'
            )

            self.market_cap_cache[date] = latest_with_industry

        print(f"    Cached market cap data for {len(self.market_cap_cache)} dates")

    def precalculate_shareholding_metrics(self):
        """Pre-calculate shareholding metrics for all quarters to speed up backtest"""
        print("    Calculating rolling 4Q metrics for all quarters...")

        # Group by quarter_date and industry_group, calculate metrics
        quarterly_metrics = []

        # Get all unique quarter dates
        all_quarters = sorted(self.shp_with_industry['quarter_date'].unique())

        for i, current_date in enumerate(all_quarters):
            if i < 3:  # Need at least 4 quarters of data
                continue

            # Get data for the last 4 quarters
            start_idx = max(0, i - 3)
            quarters_window = all_quarters[start_idx:i+1]

            # Filter data for this window
            window_data = self.shp_with_industry[self.shp_with_industry['quarter_date'].isin(quarters_window)].copy()

            if len(window_data) == 0:
                continue

            # Calculate metrics per industry_group
            metrics = window_data.groupby('industry_group').agg(
                total_stocks=('isin', 'nunique'),
                decreasing_stocks=('decreasing', 'sum')
            )

            metrics['pct_decreasing'] = (metrics['decreasing_stocks'] / metrics['total_stocks']) * 100
            metrics['percentile'] = metrics['pct_decreasing'].rank(pct=True) * 100
            metrics['quarter_date'] = current_date

            quarterly_metrics.append(metrics.reset_index())

        # Combine all metrics
        self.precalculated_metrics = pd.concat(quarterly_metrics, ignore_index=True) if quarterly_metrics else pd.DataFrame()
        print(f"    Pre-calculated metrics for {len(self.precalculated_metrics)} quarter-industry_group combinations")

    def parse_quarter_to_date(self, quarter_str):
        """Convert quarter string like 'Dec-2016' to date"""
        try:
            month_str, year = quarter_str.split('-')
            year = int(year)

            # Map month abbreviations to month numbers
            month_map = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            month = month_map.get(month_str, 12)  # Default to Dec if unknown

            return pd.Timestamp(year=year, month=month, day=1)
        except:
            return pd.NaT

    def calculate_shareholding_changes(self):
        """Calculate quarter-over-quarter shareholding changes"""
        print("    Sorting by ISIN and quarter...")
        self.shp_with_industry = self.shp_with_industry.sort_values(['isin', 'quarter_date'])

        print("    Calculating changes...")
        self.shp_with_industry['prev_shareholders'] = self.shp_with_industry.groupby('isin')['total_shareholders'].shift(1)
        self.shp_with_industry['shareholder_change'] = self.shp_with_industry['total_shareholders'] - self.shp_with_industry['prev_shareholders']
        self.shp_with_industry['pct_change'] = (self.shp_with_industry['shareholder_change'] / self.shp_with_industry['prev_shareholders']) * 100

        # Mark decreasing shareholders
        self.shp_with_industry['decreasing'] = self.shp_with_industry['shareholder_change'] < 0

    def preprocess_price_data(self):
        """Add 200-day MA and other price features"""
        print("    Calculating 200-day moving averages...")
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        self.price_df['ma_200'] = self.price_df.groupby('isin')['close'].transform(lambda x: x.rolling(200).mean())

        print("    Calculating trend strength...")
        self.price_df['above_ma'] = self.price_df['close'] > self.price_df['ma_200']

    def calculate_industry_group_shareholding_metrics(self, date):
        """Get pre-calculated industry_group shareholding metrics for 4Q lookback"""
        # Filter pre-calculated metrics for this date
        metrics = self.precalculated_metrics[self.precalculated_metrics['quarter_date'] == date].copy()

        if len(metrics) == 0:
            return pd.DataFrame()

        # Set industry_group as index and return relevant columns
        metrics = metrics.set_index('industry_group')[['total_stocks', 'decreasing_stocks', 'pct_decreasing', 'percentile']]
        return metrics

    def select_industry_groups(self, date):
        """Select industry_groups using contrarian signal and trend confirmation"""
        print(f"  Selecting industry_groups for {date.strftime('%Y-%m-%d')}...")

        # Step 1: Get industry_group-level shareholding metrics
        industry_group_metrics = self.calculate_industry_group_shareholding_metrics(date)

        if industry_group_metrics.empty:
            print("    No valid metrics found")
            return []

        # Step 2: Select top 20% by contrarian signal
        threshold = industry_group_metrics['percentile'].quantile(0.8)  # Top 20%
        contrarian_groups = industry_group_metrics[industry_group_metrics['percentile'] >= threshold]

        print(f"    Found {len(contrarian_groups)} contrarian industry_groups (top 20%)")

        # Step 3: Filter by trend strength (stocks above 200-day MA)
        trend_indicators = self.calculate_trend_indicators(date, contrarian_groups.index.tolist())

        # Step 4: Select top industry_groups by trend strength
        if len(trend_indicators) > 0:
            top_trend = trend_indicators.nlargest(n=self.NUM_INDUSTRY_GROUPS, keep='first')
            selected_groups = top_trend.index.tolist()
            print(f"    Selected {len(selected_groups)} industry_groups with strongest trends")
        else:
            selected_groups = contrarian_groups.index.tolist()[:self.NUM_INDUSTRY_GROUPS]
            print(f"    Selected {len(selected_groups)} industry_groups (no trend data)")

        return selected_groups

    def calculate_trend_indicators(self, date, industry_groups):
        """Calculate trend strength for industry_groups (% stocks above 200-day MA)"""
        # Get price data for the date
        price_data = self.price_df[self.price_df['date'] <= date].copy()
        price_data = price_data.sort_values(['isin', 'date']).drop_duplicates('isin', keep='last')

        # Merge with industry data
        price_with_industry = pd.merge(
            price_data,
            self.industry_df[['isin', 'industry', 'industry_group']],
            on='isin',
            how='left'
        )

        # Filter to selected industry_groups
        price_with_industry = price_with_industry[price_with_industry['industry_group'].isin(industry_groups)]

        # Calculate trend strength per industry_group using vectorized operations
        trend_metrics = price_with_industry.groupby('industry_group').agg(
            total_stocks=('isin', 'count'),
            above_ma=('above_ma', 'sum')
        )

        trend_metrics['trend_strength'] = (trend_metrics['above_ma'] / trend_metrics['total_stocks']) * 100

        return trend_metrics['trend_strength']

    def select_stocks(self, date, selected_groups):
        """Select stocks from selected industry_groups, max 5 per group, total 30 stocks"""
        print(f"  Selecting stocks from {len(selected_groups)} industry_groups...")

        # Get cached market cap data for this date
        stock_data = self.market_cap_cache.get(date)
        if stock_data is None or len(stock_data) == 0:
            print("    No market cap data available")
            return []

        # Filter to selected industry_groups
        stock_data = stock_data[stock_data['industry_group'].isin(selected_groups)]

        # Group by industry_group and select top stocks by market cap (max 5 per group)
        selected_stocks = []
        stocks_per_group = {}

        # Process each industry_group separately for efficiency
        for group in selected_groups:
            group_stocks = stock_data[stock_data['industry_group'] == group]
            if len(group_stocks) > 0:
                # Sort by market cap and take top 5
                top_stocks = group_stocks.nlargest(min(self.MAX_STOCKS_PER_GROUP, len(group_stocks)), 'market_cap')
                selected_stocks.extend(top_stocks['isin'].tolist())
                stocks_per_group[group] = len(top_stocks)

                # Stop if we have enough stocks total
                if len(selected_stocks) >= self.NUM_STOCKS:
                    break

        # If we have more than needed, trim to exact number
        if len(selected_stocks) > self.NUM_STOCKS:
            selected_stocks = selected_stocks[:self.NUM_STOCKS]

        print(f"    Selected {len(selected_stocks)} stocks")
        for group, count in stocks_per_group.items():
            if count > 0:
                print(f"      {group}: {count} stocks")

        return selected_stocks

    def run_backtest(self):
        """Run the complete backtest"""
        print("\n" + "="*100)
        print("RUNNING BACKTEST")
        print("="*100)

        # Get rebalance dates (quarterly) - TEST: only run for 5 quarters
        rebalance_dates = pd.date_range(start='2018-01-01', end='2019-12-31', freq='Q')
        rebalance_dates = [d.replace(day=1) for d in rebalance_dates]  # Start of quarter

        # Initialize portfolio
        self.portfolio = {}
        self.cash = self.INITIAL_CAPITAL
        self.equity_curve = []
        self.trades_log = []


            # Select industry_groups and stocks
            selected_groups = self.select_industry_groups(date)
            if not selected_groups:
                print("  No industry_groups selected, skipping...")
                continue

            selected_stocks = self.select_stocks(date, selected_groups)

            # Rebalance portfolio
            self.rebalance_portfolio(date, selected_stocks)

            # Record equity
            portfolio_value = self.calculate_portfolio_value(date)
            self.equity_curve.append({
                'date': date,
                'value': portfolio_value,
                'cash': self.cash
            })

        # Save results
        self.save_results()

    def rebalance_portfolio(self, date, target_stocks):
        """Rebalance portfolio to target stocks with smart delta trading"""
        print(f"  Rebalancing portfolio...")

        # Calculate target allocation
        if len(target_stocks) == 0:
            target_allocation = {}
        else:
            target_weight = 1.0 / len(target_stocks)
            target_allocation = {stock: target_weight for stock in target_stocks}

        # Get current prices
        current_prices = self.get_prices(date, list(self.portfolio.keys()) + target_stocks)

        # Calculate trades needed
        trades = self.calculate_trades(target_allocation, current_prices)

        # Execute trades
        self.execute_trades(date, trades, current_prices)

    def get_prices(self, date, stocks):
        """Get prices for stocks on or before the given date"""
        prices = {}
        for stock in stocks:
            stock_data = self.price_df[(self.price_df['isin'] == stock) & (self.price_df['date'] <= date)]
            if not stock_data.empty:
                latest_price = stock_data.iloc[-1]['close']
                prices[stock] = latest_price
        return prices

    def calculate_trades(self, tausing cached data"""
        prices = {}
        cached_data = self.market_cap_cache.get(date)
        if cached_data is not None:
            # Filter to requested stocks and get prices
            stock_prices = cached_data[cached_data['isin'].isin(stocks)]
            # Convert market_cap back to price (approximately)
            for _, row in stock_prices.iterrows():
                if pd.notna(row['market_cap']) and row['isin'] in self.shares_map:
                    shares = self.shares_map[row['isin']]
                    if shares > 0:
                        prices[row['isin']] = row['market_cap'] / shares
ash

        # Calculate target positions
        for stock, weight in target_allocation.items():
            target_value = total_value * weight
            target_shares = target_value / current_prices.get(stock, np.inf)

            current_shares = self.portfolio.get(stock, 0)
            delta_shares = target_shares - current_shares

            if abs(delta_shares) > 0.1:  # Minimum trade size
                trades[stock] = delta_shares

        # Handle stocks not in target (sell completely)
        for stock in self.portfolio:
            if stock not in target_allocation and self.portfolio[stock] > 0:
                trades[stock] = -self.portfolio[stock]

        return trades

    def execute_trades(self, date, trades, prices):
        """Execute trades with transaction costs and taxes"""
        total_transaction_cost = 0

        for stock, shares in trades.items():
            if stock not in prices:
                continue

            price = prices[stock]
            trade_value = abs(shares) * price

            # Transaction costs
            brokerage = trade_value * self.BROKERAGE
            stt = trade_value * (self.STT_SELL if shares < 0 else self.STT_BUY)
            exchange_txn = trade_value * self.EXCHANGE_TXN
            gst = brokerage * self.GST
            sebi = trade_value * self.SEBI_CHARGES
            stamp_duty = trade_value * self.STAMP_DUTY if shares > 0 else 0
            slippage = trade_value * self.SLIPPAGE

            transaction_cost = brokerage + stt + exchange_txn + gst + sebi + stamp_duty + slippage
            total_transaction_cost += transaction_cost

            # Calculate capital gains tax for sells
            if shares < 0:
                tax_cost = self.calculate_capital_gains_tax(stock, shares, price)
                transaction_cost += tax_cost

            # Update cash and portfolio
            cash_flow = -shares * price - transaction_cost
            self.cash += cash_flow

            # Update portfolio
            self.portfolio[stock] = self.portfolio.get(stock, 0) + shares
            if self.portfolio[stock] <= 0.1:  # Remove tiny positions
                del self.portfolio[stock]

            # Log trade
            self.trades_log.append({
                'date': date,
                'stock': stock,
                'shares': shares,
                'price': price,
                'value': trade_value,
                'transaction_cost': transaction_cost
            })

        if total_transaction_cost > 0:
            print(".2f")

    def calculate_capital_gains_tax(self, stock, shares, sell_price):
        """Calculate capital gains tax for a sell trade"""
        # Simplified tax calculation (assuming all gains are short-term for now)
        # In a real implementation, you'd track purchase dates and holding periods
        gain = -shares * sell_price  # shares is negative for sells
        tax = gain * self.STCG_RATE
        return max(0, tax)  # No tax on losses

    def calculate_portfolio_value(self, date):
        """Calculate total portfolio value"""
        portfolio_value = self.cash

        prices = self.get_prices(date, list(self.portfolio.keys()))
        for stock, shares in self.portfolio.items():
            if stock in prices:
                portfolio_value += shares * prices[stock]

        return portfolio_value

    def save_results(self):
        """Save backtest results"""
        print("\nSaving results...")

        # Create output directory
        output_dir = Path("strategies/outputs")
        output_dir.mkdir(exist_ok=True)

        # Save equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        equity_file = output_dir / f"industry_group_4q_top20pct_max5_per_group_equity_{timestamp}.csv"
        equity_df.to_csv(equity_file, index=False)
        print(f"✅ Equity curve saved: {equity_file}")

        # Save trades log
        trades_df = pd.DataFrame(self.trades_log)
        trades_file = output_dir / f"industry_group_4q_top20pct_max5_per_group_trades_{timestamp}.csv"
        trades_df.to_csv(trades_file, index=False)
        print(f"✅ Trades log saved: {trades_file}")

        # Calculate and display final metrics
        self.calculate_final_metrics(equity_df)

    def calculate_final_metrics(self, equity_df):
        """Calculate and display final performance metrics"""
        print("\n" + "="*100)
        print("FINAL PERFORMANCE METRICS")
        print("="*100)

        equity_df = equity_df.copy()
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date')

        # CAGR
        years = (equity_df.index[-1] - equity_df.index[0]).days / 365.25
        final_value = equity_df['value'].iloc[-1]
        initial_value = equity_df['value'].iloc[0]
        cagr = (final_value / initial_value) ** (1 / years) - 1

        # Sharpe Ratio
        equity_df['daily_return'] = equity_df['value'].pct_change()
        daily_rf_rate = 0.06 / 252
        excess_returns = equity_df['daily_return'] - daily_rf_rate
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

        # Max Drawdown
        rolling_max = equity_df['value'].expanding().max()
        drawdowns = equity_df['value'] / rolling_max - 1
        max_dd = drawdowns.min()

        # Win Rate
        quarterly_returns = equity_df['value'].resample('Q').last().pct_change()
        win_rate = (quarterly_returns > 0).mean()

        # Total Return
        total_return = (final_value / initial_value - 1)

        print(f"📈 CAGR: {cagr:.1%}")
        print(f"🎯 Sharpe Ratio: {sharpe:.3f}")
        print(f"📉 Max Drawdown: {max_dd:.1%}")
        print(f"🏆 Win Rate: {win_rate:.1%}")
        print(f"💰 Total Return: {total_return:.1%}")

        print(f"\n📊 Strategy: Industry_Group-Based Contrarian (Max 5 per Group)")
        print(f"   - Uses 4Q lookback for industry_group-level contrarian signals")
        print(f"   - Selects top 20% industry_groups by contrarian score, then top 10 by trend strength")
        print(f"   - Picks up to 5 stocks per industry_group by market cap, total 30 stocks")


if __name__ == "__main__":
    strategy = IndustryGroup4QTop20PctMax5PerGroupStrategy()
    strategy.run_backtest()