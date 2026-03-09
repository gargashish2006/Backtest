"""
Frictionless comparison of 5 Top-1000 variants:
1. Baseline (Index)
2. SH Decrease (1Q)
3. SH Decrease (4Q)
4. MCPS Increase (1Q)
5. MCPS Increase (4Q)
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
from data.data_handler import DataHandler
from engine.sim_engine import SimEngine
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from utils.analytics import calculate_metrics

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

class Top1000VariantStrategy:
    def __init__(self, data_handler, mode):
        self.dh = data_handler
        self.mode = mode
        self.sh_df = data_handler.shareholding_df

    def _get_q_labels(self, date, lag):
        y, m = date.year, date.month
        if m == 2: q = f"Dec-{y-1}"
        elif m == 5: q = f"Mar-{y}"
        elif m == 8: q = f"Jun-{y}"
        else: q = f"Sep-{y}"
        
        months = [2, 5, 8, 11]
        m_idx = months.index(m)
        target_idx = (m_idx - lag) % 4
        year_offset = (m_idx - lag) // 4
        target_year = y + year_offset
        target_month = months[target_idx]
        
        if target_month == 2: prev_q = f"Dec-{target_year-1}"
        elif target_month == 5: prev_q = f"Mar-{target_year}"
        elif target_month == 8: prev_q = f"Jun-{target_year}"
        else: prev_q = f"Sep-{target_year}"
        
        return q, prev_q

    def calculate_selection(self, date):
        top_1000 = self.dh.get_universe(date, size=1000)
        if top_1000.empty: return {}
        
        if self.mode == 'baseline':
            isins = top_1000['isin'].tolist()
        else:
            lag = 1 if '1Q' in self.mode else 4
            curr_q, prev_q = self._get_q_labels(date, lag)
            
            curr_sh = self.sh_df[self.sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
            prev_sh = self.sh_df[self.sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
            
            if curr_sh.empty or prev_sh.empty:
                return {}
            
            merged = pd.merge(top_1000, curr_sh, on='isin')
            merged = pd.merge(merged, prev_sh, on='isin')
            
            if self.mode.startswith('SH_Dec'):
                selected = merged[merged['curr'] < merged['prev']]
            elif self.mode.startswith('MCPS_Incr'):
                all_dates = sorted(self.dh.get_all_dates())
                valid_prev_dates = [d for d in all_dates if d <= date - pd.Timedelta(days=90 if lag==1 else 365)]
                if not valid_prev_dates: return {}
                prev_date = max(valid_prev_dates)
                
                prev_prices = self.dh.price_df[self.dh.price_df['date'] == prev_date][['isin', 'mc']].rename(columns={'mc': 'mc_prev'})
                merged = pd.merge(merged, prev_prices, on='isin')
                
                merged['mcps_curr'] = merged['mc'] / merged['curr']
                merged['mcps_prev'] = merged['mc_prev'] / merged['prev']
                selected = merged[merged['mcps_curr'] > merged['mcps_prev']]
            else:
                selected = merged
                
            isins = selected['isin'].tolist()

        if not isins: return {}
        weight = 1.0 / len(isins)
        return {isin: weight for isin in isins}

def run_sim(mode):
    start_date, end_date = "2018-01-01", "2026-02-05"
    all_dates = sorted(dh.get_all_dates())
    rebalance_dates = sorted([
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2018, 2027) for m in [2, 5, 8, 11]
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ])
    rebalance_dates = [d for d in rebalance_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

    strat = Top1000VariantStrategy(dh, mode)
    port = Portfolio(10000000)
    fee_model = FeeModel(0, 0)
    tax_man = TaxManager(0, 0)
    
    eng = SimEngine(dh, port, fee_model, tax_man, cash_yield_rate=0)
    eng.run(start_date, end_date, strat.calculate_selection, rebalance_dates, verbose=False)
    
    return pd.DataFrame(port.nav_history)

modes = ['baseline', 'SH_Decr_1Q', 'SH_Decr_4Q', 'MCPS_Incr_1Q', 'MCPS_Incr_4Q']
all_navs = {}

print(f"{'Mode':<15} | {'CAGR':<10} | {'MaxDD':<10} | {'Sharpe':<10}")
print("-" * 55)

for m in modes:
    nav_df = run_sim(m)
    metrics = calculate_metrics(nav_df)
    print(f"{m:<15} | {metrics['CAGR']:<10} | {metrics['Max Drawdown']:<10} | {metrics['Sharpe Ratio']:<10}")
    all_navs[m] = nav_df

fig, ax = plt.subplots(figsize=(15, 8))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

colors = ['#aaaaaa', '#00d4ff', '#00ff88', '#ff9500', '#ff2e63']
for i, m in enumerate(modes):
    df = all_navs[m]
    ax.plot(df['date'], df['nav'] / df['nav'].iloc[0] * 100, label=m, color=colors[i], linewidth=2)

ax.set_title("Top 1000 Selection Variants: SH cleaning vs. MCPS Growth", color='white', fontsize=18)
ax.set_ylabel("Normalized NAV", color='white')
ax.legend(facecolor='#1a1a2e', labelcolor='white')
ax.grid(True, color='#222222')
ax.tick_params(colors='white')

out_path = repo_root / "top1000_variants_comparison.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved comparison plot to: {out_path}")
plt.show()
