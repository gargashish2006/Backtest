import pandas as pd
import pathlib
from typing import Dict, List, Optional
from pathlib import Path

class DataHandler:
    """Efficiently loads and handles lookup for historical price data."""
    def __init__(self, price_parquet_path: str):
        self.price_path = pathlib.Path(price_parquet_path)
        self.price_df: Optional[pd.DataFrame] = None
        self.cached_prices: Dict[pd.Timestamp, Dict[str, float]] = {}
        self.industry_benchmarks: Dict[str, pd.DataFrame] = {}
        self.isin_to_industry: Dict[str, str] = {}
        self.isin_to_group: Dict[str, str] = {}
        self.isin_to_name: Dict[str, str] = {}
        self.shareholding_df: Optional[pd.DataFrame] = None
        self.first_date_map: Dict[str, pd.Timestamp] = {}
        self.top_100_bench: Optional[pd.DataFrame] = None
        self.top_1000_bench: Optional[pd.DataFrame] = None

    def load_data(self):
        """Loads price and metadata, calculates market cap."""
        print(f"Loading price data from {self.price_path}...")
        self.price_df = pd.read_parquet(self.price_path)
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.first_date_map = self.price_df.groupby('isin')['date'].min().to_dict()
        
        # Load outstanding shares
        shares_path = self.price_path.parent / "outstanding_shares.csv"
        if shares_path.exists():
            shares_df = pd.read_csv(shares_path)
            shares_map = dict(zip(shares_df['isin'], shares_df['total_outstanding_shares']))
            self.price_df['shares'] = self.price_df['isin'].map(shares_map)
            self.price_df['mc'] = self.price_df['close'] * self.price_df['shares']
            self.price_df['traded_val'] = self.price_df['close'] * self.price_df['volume']
            
        # Load Industry Mapping
        industry_path = self.price_path.parent / "industry_info.csv"
        if industry_path.exists():
            industry_df = pd.read_csv(industry_path)
            self.isin_to_industry = dict(zip(industry_df['isin'], industry_df['industry']))
            self.isin_to_group = dict(zip(industry_df['isin'], industry_df['industry_group']))
            self.isin_to_name = dict(zip(industry_df['isin'], industry_df['company_name']))
        else:
            self.isin_to_industry = {}
            self.isin_to_group = {}
            self.isin_to_name = {}
            
        # Load Shareholding Patterns
        sh_path = self.price_path.parent / "shareholding_patterns.parquet"
        if sh_path.exists():
            self.shareholding_df = pd.read_parquet(sh_path)
            # Ensure quarter column is clean and sortable if needed, though they are likely strings like 'Dec-2025'
        
        print(f"Loaded {len(self.price_df)} rows of data.")

    def load_benchmarks(self, benchmark_dir: Path):
        """Loads broad indices for performance baseline."""
        self.top_100_bench = pd.read_parquet(benchmark_dir / "Benchmark_100_equalWeight.parquet")
        self.top_100_bench['date'] = pd.to_datetime(self.top_100_bench['date'])
        self.top_1000_bench = pd.read_parquet(benchmark_dir / "Benchmark_1000_equalWeight.parquet")
        self.top_1000_bench['date'] = pd.to_datetime(self.top_1000_bench['date'])
        
        # Load NIFTY 500
        indices_path = self.price_path.parent / "indices_data.parquet"
        if indices_path.exists():
            df_idx = pd.read_parquet(indices_path)
            n500 = df_idx[df_idx['index_name'] == 'NIFTY 500'].copy()
            n500 = n500.rename(columns={'close': 'index_value'})
            n500['date'] = pd.to_datetime(n500['date'])
            self.nifty_500_bench = n500
        else:
            self.nifty_500_bench = None

    def get_daily_metrics(self, date: pd.Timestamp) -> pd.DataFrame:
        """Returns a DataFrame of all metrics for a specific date."""
        return self.price_df[self.price_df['date'] == date].copy()

    def get_daily_prices(self, date: pd.Timestamp) -> Dict[str, float]:
        """Returns a dict of isin -> close price for a specific date."""
        if date in self.cached_prices:
            return self.cached_prices[date]
        
        day_data = self.price_df[self.price_df['date'] == date]
        if day_data.empty:
            return {}
            
        prices = dict(zip(day_data['isin'], day_data['close']))
        self.cached_prices[date] = prices
        return prices

    def get_all_dates(self) -> List[pd.Timestamp]:
        """Returns sorted list of all unique dates in the dataset."""
        if self.price_df is None: return []
        return sorted(self.price_df['date'].unique())

    def get_universe_on_date(self, date: pd.Timestamp) -> List[str]:
        """Returns list of ISINs active on a particular date."""
        day_prices = self.get_daily_prices(date)
        return list(day_prices.keys())

    def get_universe(self, date: pd.Timestamp, size: int = 1000) -> pd.DataFrame:
        """Returns the top N stocks by market cap on a given date."""
        day_data = self.price_df[self.price_df['date'] == date]
        if day_data.empty:
            return pd.DataFrame()
        return day_data.sort_values('mc', ascending=False).head(size)

    def get_industry_for_isin(self, isin: str) -> str:
        return self.isin_to_industry.get(isin, "Unknown")

    def get_industry_benchmark_price(self, industry: str, date: pd.Timestamp) -> float:
        """Loads and returns industry benchmark price on a given date with robust mapping."""
        if industry not in self.industry_benchmarks:
            base_dir = self.price_path.parent.parent / "benchmarks" / "industries"
            
            # Robust slugs to try
            slugs = [
                industry.replace(" ", "_"),
                industry.replace(" ", "_").replace("&", "_"),
                industry.replace(" ", "_").replace("/", "__"),
                industry.replace(" ", "_").replace("&", "_").replace("-", "_").replace("/", "__").replace("(", "_").replace(")", "_"),
            ]
            
            benchmark_path = None
            for s in slugs:
                p = base_dir / s / "timeseries.parquet"
                if p.exists():
                    benchmark_path = p
                    break
                p = base_dir / s / "timeseries.csv"
                if p.exists():
                    benchmark_path = p
                    break

            if benchmark_path:
                if benchmark_path.suffix == ".parquet":
                    df = pd.read_parquet(benchmark_path)
                else:
                    df = pd.read_csv(benchmark_path)
                df['date'] = pd.to_datetime(df['date'])
                self.industry_benchmarks[industry] = df.sort_values('date')
            else:
                return 0.0
        
        df = self.industry_benchmarks[industry]
        match = df[df['date'] <= date]
        if match.empty: return 0.0
        return float(match.iloc[-1]['index_value'])

    def get_shareholder_trend(self, date: pd.Timestamp, lookback_quarters: int = 4) -> pd.DataFrame:
        """
        Calculates shareholder trend for all stocks.
        Returns DataFrame: [isin, current_sh, prev_sh, decreased]
        Uses most recent quarter vs N quarters ago (default 4=1 year).
        """
        if self.shareholding_df is None:
            return pd.DataFrame()

        # Quarter mapping logic: 
        year = date.year
        month = date.month
        
        # Determine the "Current" Quarter (most recent available)
        if month >= 2 and month < 5:
            curr_q_idx = 0 # Dec-{year-1}
            base_year = year - 1
            start_code = "Dec"
        elif month >= 5 and month < 8:
            curr_q_idx = 1 # Mar-{year}
            base_year = year
            start_code = "Mar"
        elif month >= 8 and month < 11:
            curr_q_idx = 2 # Jun-{year}
            base_year = year
            start_code = "Jun"
        else: # Nov or Jan
            curr_q_idx = 3 # Sep-{year}
            base_year = year if month >= 11 else year - 1
            start_code = "Sep"
            
        curr_q = f"{start_code}-{base_year}"
        
        # Calculate Previous Quarter based on lookback
        # Quarters sequence: Mar, Jun, Sep, Dec
        quarters = ["Mar", "Jun", "Sep", "Dec"]
        
        # Convert current into a linear index
        # 0=Mar, 1=Jun, 2=Sep, 3=Dec
        # But our start codes are different... let's align
        # Mar-Y is (Y * 4) + 0
        # Jun-Y is (Y * 4) + 1
        # Sep-Y is (Y * 4) + 2
        # Dec-Y is (Y * 4) + 3
        
        if start_code == "Mar": linear_curr = (base_year * 4) + 0
        elif start_code == "Jun": linear_curr = (base_year * 4) + 1
        elif start_code == "Sep": linear_curr = (base_year * 4) + 2
        else: linear_curr = (base_year * 4) + 3 # Dec
        
        linear_prev = linear_curr - lookback_quarters
        prev_year = linear_prev // 4
        prev_q_idx = linear_prev % 4
        prev_code = quarters[prev_q_idx]
        
        prev_q = f"{prev_code}-{prev_year}"
            
        # Extract slices for current and previous quarters
        curr_slice = self.shareholding_df[self.shareholding_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr_sh'})
        prev_slice = self.shareholding_df[self.shareholding_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev_sh'})
        
        # Explicitly ignore missing or invalid (0) data points
        curr_slice = curr_slice[(curr_slice['curr_sh'].notna()) & (curr_slice['curr_sh'] > 0)]
        prev_slice = prev_slice[(prev_slice['prev_sh'].notna()) & (prev_slice['prev_sh'] > 0)]
        
        merged = pd.merge(curr_slice, prev_slice, on='isin', how='inner')
        merged['decreased'] = merged['curr_sh'] < merged['prev_sh']
        
        return merged

    def get_weekly_low_3_cache(self) -> pd.DataFrame:
        """
        Pre-computes a DataFrame of 3-Weekly Lowest Weekly Close for ALL stocks.
        Index: Daily Date (forward filled from weekly)
        Columns: ISIN
        Logic: Min of current Friday and previous 2 Friday closes.
        """
        print("Pre-computing 3-Week Low Cache (Vectorized)...")
        if self.price_df is None: return pd.DataFrame()
        
        # 1. Pivot to Wide Format
        pivot_df = self.price_df.pivot(index='date', columns='isin', values='close')
        
        # 2. Resample to Weekly (Friday)
        weekly_df = pivot_df.resample('W-FRI').last()
        
        # 3. Calculate Rolling 3-week Min
        # min_periods=1 ensures we get some value even at start
        low_3_df = weekly_df.rolling(window=3, min_periods=1).min()
        
        # 4. Reindex back to Daily (Forward Fill)
        daily_low = low_3_df.reindex(pivot_df.index).ffill()
        
        print("3-Week Low Cache Complete.")
        return daily_low

    def get_prev_month_low_cache(self) -> pd.DataFrame:
        """
        Pre-computes a DataFrame of the lowest close of the PREVIOUS month for ALL stocks.
        Index: Daily Date
        Columns: ISIN
        Logic: On any day in Month M, the value is min(Closes in Month M-1).
        """
        print("Pre-computing Prev Month Low Cache (Vectorized)...")
        if self.price_df is None: return pd.DataFrame()
        
        # 1. Pivot to Wide Format
        pivot_df = self.price_df.pivot(index='date', columns='isin', values='close')
        
        # 2. Resample to Monthly Low
        monthly_low = pivot_df.resample('MS').min() # MS = Month Start, value is min for that month
        
        # 3. Shift by 1 month (so Month M sees Month M-1's low)
        prev_month_low = monthly_low.shift(1)
        
        # 4. Reindex back to Daily (Forward Fill)
        daily_low = prev_month_low.reindex(pivot_df.index).ffill()
        
        print("Prev Month Low Cache Complete.")
        return daily_low

    def get_weekly_rsi_cache(self) -> pd.DataFrame:
        """
        Pre-computes a DataFrame of Weekly RSI(14) values for ALL stocks.
        Index: Daily Date (forward filled from weekly)
        Columns: ISIN
        """
        print("Pre-computing Weekly RSI Cache (Vectorized)...")
        if self.price_df is None: return pd.DataFrame()
        
        # 1. Pivot to Wide Format (Index=Date, Col=ISIN, Val=Close)
        # Filter for minimal necessary columns to save memory
        pivot_df = self.price_df.pivot(index='date', columns='isin', values='close')
        
        # 2. Resample to Weekly (Friday)
        weekly_df = pivot_df.resample('W-FRI').last()
        
        # 3. Calculate RSI(14) Vectorized
        delta = weekly_df.diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        # Wilder's Smoothing (alpha = 1/n)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        # Handle division by zero (infinite RS) -> RSI = 100
        rsi_df = 100 - (100 / (1 + rs))
        rsi_df = rsi_df.fillna(0) # or NaN, but 0 is safe for > comparison
        
        # 4. Reindex back to Daily (Forward Fill)
        # This allows O(1) lookup on any simulation date
        daily_rsi = rsi_df.reindex(pivot_df.index).ffill()
        
        print("RSI Cache Benchmark Complete.")
        return daily_rsi
