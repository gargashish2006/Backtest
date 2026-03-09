
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.contrarian_breadth import ContrarianBreadthStrategy
from utils.analytics import calculate_metrics
import matplotlib.pyplot as plt

class SmartMoneyStabilityStrategy(ContrarianBreadthStrategy):
    """
    Inherits from ContrarianBreadthStrategy but adds a final filter:
    Selected stocks MUST have Stable or Increasing Smart Money Holdings over the last year.
    Smart Money = Promoter % + FII % + DII %
    (Current Smart Money % >= 1 Year Ago Smart Money %)
    """
    def calculate_selection(self, date: pd.Timestamp):
        # 1. Get standard candidates from parent (Group/Industry filters + RSNP)
        candidates = super().calculate_selection(date)
        if not candidates:
            return {}
            
        candidate_isins = list(candidates.keys())
        
        # 2. Get Smart Money Trend
        if self.dh.shareholding_df is None:
            return {}

        # Determine Quarters (Current vs 1 Year Ago)
        year = date.year
        month = date.month
        
        if month >= 2 and month < 5:
            start_code, base_year = "Dec", year - 1
        elif month >= 5 and month < 8:
            start_code, base_year = "Mar", year
        elif month >= 8 and month < 11:
            start_code, base_year = "Jun", year
        else: 
            start_code, base_year = "Sep", year
            
        curr_q = f"{start_code}-{base_year}"
        
        # Calculate Previous Quarter (4 quarters ago)
        quarters = ["Mar", "Jun", "Sep", "Dec"]
        if start_code == "Mar": linear_curr = (base_year * 4) + 0
        elif start_code == "Jun": linear_curr = (base_year * 4) + 1
        elif start_code == "Sep": linear_curr = (base_year * 4) + 2
        else: linear_curr = (base_year * 4) + 3 # Dec
        
        linear_prev = linear_curr - self.shareholder_lookback_quarters
        prev_year = linear_prev // 4
        prev_q_idx = linear_prev % 4
        prev_code = quarters[prev_q_idx]
        prev_q = f"{prev_code}-{prev_year}"
        
        # Filter DF for current and prev quarters
        cols = ['isin', 'promoter_holding_pct', 'fii_holding_pct', 'dii_holding_pct']
        
        curr_slice = self.dh.shareholding_df[self.dh.shareholding_df['quarter'] == curr_q][cols].copy()
        prev_slice = self.dh.shareholding_df[self.dh.shareholding_df['quarter'] == prev_q][cols].copy()
        
        # Calculate Total Smart Money
        curr_slice['smart_money'] = curr_slice['promoter_holding_pct'].fillna(0) + \
                                    curr_slice['fii_holding_pct'].fillna(0) + \
                                    curr_slice['dii_holding_pct'].fillna(0)
                                    
        prev_slice['smart_money'] = prev_slice['promoter_holding_pct'].fillna(0) + \
                                    prev_slice['fii_holding_pct'].fillna(0) + \
                                    prev_slice['dii_holding_pct'].fillna(0)
        
        curr_slice = curr_slice[['isin', 'smart_money']].rename(columns={'smart_money': 'curr_sm'})
        prev_slice = prev_slice[['isin', 'smart_money']].rename(columns={'smart_money': 'prev_sm'})
        
        merged = pd.merge(curr_slice, prev_slice, on='isin', how='inner')
        
        # STABILITY FILTER: Current >= Previous
        merged['stable_smart_money'] = merged['curr_sm'] >= merged['prev_sm']
        
        valid_smart_money = set(merged[merged['stable_smart_money'] == True]['isin'])
        
        final_selection = [isin for isin in candidate_isins if isin in valid_smart_money]
        
        if not final_selection:
            return {}
            
        # Return equal weights
        weight = 1.0 / len(final_selection)
        return {isin: weight for isin in final_selection}

def run_smart_money_stability_analysis():
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()
    
    # Quarterly Rebalance (Standard Champion Schedule)
    rebalance_dates = []
    for year in range(2017, 2027):
        for month in [2, 5, 8, 11]:
            d = pd.Timestamp(year=year, month=month, day=15)
            valid = [dt for dt in all_dates if dt <= d]
            if valid: rebalance_dates.append(max(valid))
    
    rebalance_dates.sort()
    start_date = "2017-05-15"
    end_date = "2026-02-05"
    rebalance_dates = [d for d in rebalance_dates if d >= pd.Timestamp(start_date)]

    print(f"Starting Smart Money Stability Filter Analysis...")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")

    strategy = SmartMoneyStabilityStrategy(dh, num_stocks=15, max_per_industry=3)
    portfolio = Portfolio(initial_cash=10000000)
    fee_model = FeeModel(transaction_fee_rate=0.0015, impact_cost_rate=0.005)
    tax_man = TaxManager(stcg_rate=0.20, ltcg_rate=0.125)
    engine = SimEngine(dh, portfolio, fee_model, tax_man, cash_yield_rate=0.05, cash_tax_rate=0.30)
    
    engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_func=strategy.calculate_selection,
        rebalance_dates=rebalance_dates,
        verbose=False
    )
    
    nav_df = pd.DataFrame(portfolio.nav_history)
    stats = calculate_metrics(nav_df)
    
    print("\n" + "="*60)
    print("SMART MONEY STABILITY FILTER PERFORMANCE")
    print("="*60)
    for k, v in stats.items():
        print(f"{k:<25}: {v}")
        
    print("\n" + "="*60)
    print("COMPARISON VS CHAMPION BASELINE")
    print("="*60)
    print(f"{'Metric':<20} | {'Smart Money Stable':<18} | {'Champion':<15}")
    print("-" * 60)
    print(f"{'CAGR (%)':<20} | {stats['CAGR']:>18} | {'22.54%':>15}")
    print(f"{'Max Drawdown (%)':<20} | {stats['Max Drawdown']:>18} | {'-41.09%':>15}")
    print("="*60)

    # Plot Comparison
    baseline_path = repo_root / "outputs/final_champion_nav.csv"
    if baseline_path.exists():
        champ_nav = pd.read_csv(baseline_path)
        champ_nav['date'] = pd.to_datetime(champ_nav['date'])
        champ_nav = champ_nav.set_index('date')['nav']
        
        sm_nav = nav_df.set_index('date')['nav']
        
        combined = pd.DataFrame({'Smart Money Stability': sm_nav, 'Champion': champ_nav}).dropna()
        
        plt.figure(figsize=(12, 6))
        plt.plot(combined.index, combined['Champion'], label='Champion (Sector Only)', alpha=0.7)
        plt.plot(combined.index, combined['Smart Money Stability'], label='Smart Money Filter', linewidth=2)
        
        plt.title('Smart Money Stability Filter vs Champion Strategy')
        plt.xlabel('Date')
        plt.ylabel('NAV')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        output_path = repo_root / "outputs/smart_money_vs_champion.png"
        plt.savefig(output_path)
        print(f"\nChart saved to: {output_path}")

if __name__ == "__main__":
    run_smart_money_stability_analysis()
