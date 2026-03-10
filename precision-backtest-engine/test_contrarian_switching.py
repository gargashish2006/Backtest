"""
Contrarian Benchmark Switching Backtest (Frictionless)
Rule: 
- If Breadth(Top 200) > Breadth(Mid), Buy Top 1000
- If Breadth(Mid) > Breadth(Top 200), Buy Top 200
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

s = MCPSStrategy(dh)
all_dates = dh.get_all_dates()

# Rebalance quarterly
rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp("2017-05-15") <= d <= pd.Timestamp("2026-02-05")]

price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close').ffill()

def get_segment_breadth(date):
    signal_date = date - pd.Timedelta(days=7)
    actual_signal_date = max([d for d in all_dates if d <= signal_date])
    universe_1000 = dh.get_universe(actual_signal_date, size=1000)
    seg_a = universe_1000.iloc[:200]['isin'].tolist()
    seg_b = universe_1000.iloc[200:]['isin'].tolist()
    
    curr_q, prev_q = s._get_quarter_labels(actual_signal_date, 4)
    sh_df = dh.shareholding_df
    
    curr_sh = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'curr'})
    prev_sh = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'prev'})
    merged = pd.merge(curr_sh, prev_sh, on='isin')
    merged['decreased'] = merged['curr'] < merged['prev']
    
    b_a = merged[merged['isin'].isin(seg_a)]['decreased'].mean()
    b_b = merged[merged['isin'].isin(seg_b)]['decreased'].mean()
    return b_a, b_b

# ── Backtest Loop ─────────────────────────────────────────────────────────────
initial_cash = 10_000_000
p_switch = initial_cash
p_t200 = initial_cash
p_t1000 = initial_cash

history = []

curr_holding_switch = []
curr_holding_t200 = []
curr_holding_t1000 = []

for i, rd in enumerate(rdates):
    # End of period value for previous holdings
    if i > 0:
        prev_rd = rdates[i-1]
        
        def calc_nav(holding, prev_val):
            if not holding: return prev_val
            valid = [i for i in holding if i in price_pivot.columns]
            start_prices = price_pivot.loc[prev_rd, valid]
            end_prices = price_pivot.loc[rd, valid]
            ret = (end_prices / start_prices).mean()
            return prev_val * ret

        p_switch = calc_nav(curr_holding_switch, p_switch)
        p_t200 = calc_nav(curr_holding_t200, p_t200)
        p_t1000 = calc_nav(curr_holding_t1000, p_t1000)

    # Rebalance
    b_a, b_b = get_segment_breadth(rd)
    
    universe_1000 = dh.get_universe(rd, size=1000)
    isins_1000 = universe_1000['isin'].tolist()
    isins_200 = universe_1000.iloc[:200]['isin'].tolist()
    
    curr_holding_t200 = isins_200
    curr_holding_t1000 = isins_1000
    
    # Switcher Logic
    # If B(200) > B(Mid) -> Buy Top 1000
    if b_a > b_b:
        curr_holding_switch = isins_1000
        regime = "Top 1000"
    else:
        curr_holding_switch = isins_200
        regime = "Top 200"
        
    history.append({
        'date': rd,
        'NAV_Switch': p_switch,
        'NAV_T200': p_t200,
        'NAV_T1000': p_t1000,
        'Regime': regime,
        'Breadth_200': b_a,
        'Breadth_Mid': b_b
    })

df_hist = pd.DataFrame(history).set_index('date')

# Metrics
def get_stats(nav_series):
    # Very simple metrics for the summary
    cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (1 / (len(nav_series)/4)) - 1
    dd = (nav_series / nav_series.cummax() - 1).min()
    return f"{cagr*100:.2f}%", f"{dd*100:.2f}%"

print("\n" + "=" * 60)
print(f"{'Strategy':<20} | {'CAGR':^15} | {'Max DD':^15}")
print("-" * 60)
print(f"{'Static Top 200':<20} | {get_stats(df_hist['NAV_T200'])[0]:^15} | {get_stats(df_hist['NAV_T200'])[1]:^15}")
print(f"{'Static Top 1000':<20} | {get_stats(df_hist['NAV_T1000'])[0]:^15} | {get_stats(df_hist['NAV_T1000'])[1]:^15}")
print(f"{'Switcher (Contr.)':<20} | {get_stats(df_hist['NAV_Switch'])[0]:^15} | {get_stats(df_hist['NAV_Switch'])[1]:^15}")
print("=" * 60)

# Plot
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(df_hist.index, df_hist['NAV_T200'] / initial_cash * 100, color='#00d4ff', label='Top 200')
ax.plot(df_hist.index, df_hist['NAV_T1000'] / initial_cash * 100, color='#6bcb77', label='Top 1000')
ax.plot(df_hist.index, df_hist['NAV_Switch'] / initial_cash * 100, color='#f4a261', linewidth=3, label='Switcher (Contrarian)')

# Add vertical bars for regimes
for i in range(len(df_hist)-1):
    d1 = df_hist.index[i]
    d2 = df_hist.index[i+1]
    reg = df_hist.iloc[i]['Regime']
    color = '#6bcb77' if reg == 'Top 1000' else '#00d4ff'
    ax.axvspan(d1, d2, color=color, alpha=0.1)

ax.set_title("Contrarian Benchmark Switcher vs Static Benchmarks", color='white', fontsize=16)
ax.tick_params(colors='white')
ax.grid(True, color='#222222')
ax.legend(facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "contrarian_benchmark_switcher.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved plot to: {out_path}")
plt.show()
