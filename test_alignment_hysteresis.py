"""
Alignment Benchmark Switching with Hysteresis (10% Buffer)
Rule:
- Switch to T1000 if Breadth(Mid) > Breadth(T200) + 10%
- Switch to T200 if Breadth(T200) > Breadth(Mid) + 10%
- Else, stay with current holding.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

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
p_hyst = initial_cash
p_align = initial_cash

history = []

curr_holding_hyst = []
curr_regime_hyst = "Top 1000" # Initial default

curr_holding_align = []

for i, rd in enumerate(rdates):
    if i > 0:
        prev_rd = rdates[i-1]
        def calc_nav(holding, prev_val):
            if not holding: return prev_val
            valid = [i for i in holding if i in price_pivot.columns]
            start_prices = price_pivot.loc[prev_rd, valid]
            end_prices = price_pivot.loc[rd, valid]
            return prev_val * (end_prices / start_prices).mean()

        p_hyst = calc_nav(curr_holding_hyst, p_hyst)
        p_align = calc_nav(curr_holding_align, p_align)

    # Rebalance logic
    b_a, b_b = get_segment_breadth(rd)
    universe_1000 = dh.get_universe(rd, size=1000)
    isins_1000 = universe_1000['isin'].tolist()
    isins_200 = universe_1000.iloc[:200]['isin'].tolist()
    
    # Standard Alignment (Threshold 0)
    if b_a > b_b:
        curr_holding_align = isins_200
        align_reg = "Top 200"
    else:
        curr_holding_align = isins_1000
        align_reg = "Top 1000"
        
    # Hysteresis Alignment (Threshold 0.10)
    buffer = 0.10
    if curr_regime_hyst == "Top 1000":
        # Switch to T200 ONLY IF B(200) > B(Mid) + 10%
        if b_a > (b_b + buffer):
            curr_regime_hyst = "Top 200"
    elif curr_regime_hyst == "Top 200":
        # Switch to T1000 ONLY IF B(Mid) > B(200) + 10%
        if b_b > (b_a + buffer):
            curr_regime_hyst = "Top 1000"
            
    curr_holding_hyst = isins_200 if curr_regime_hyst == "Top 200" else isins_1000
        
    history.append({
        'date': rd,
        'NAV_Hyst': p_hyst,
        'NAV_Align': p_align,
        'Regime_Hyst': curr_regime_hyst,
        'Regime_Align': align_reg,
        'B_Diff': b_a - b_b
    })

df_hist = pd.DataFrame(history).set_index('date')

def get_stats(nav_series):
    cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (1 / (len(nav_series)/4)) - 1
    dd = (nav_series / nav_series.cummax() - 1).min()
    return f"{cagr*100:.2f}%", f"{dd*100:.2f}%"

print("\n" + "=" * 60)
print(f"{'Strategy':<20} | {'CAGR':^15} | {'Max DD':^15}")
print("-" * 60)
print(f"{'Alignment (0% Buf)':<20} | {get_stats(df_hist['NAV_Align'])[0]:^15} | {get_stats(df_hist['NAV_Align'])[1]:^15}")
print(f"{'Hysteresis (10% Buf)':<20} | {get_stats(df_hist['NAV_Hyst'])[0]:^15} | {get_stats(df_hist['NAV_Hyst'])[1]:^15}")
print("=" * 60)

# Plot
fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(df_hist.index, df_hist['NAV_Align'] / initial_cash * 100, color='#ff9f1c', alpha=0.6, label='Alignment (Zero Buffer)')
ax.plot(df_hist.index, df_hist['NAV_Hyst'] / initial_cash * 100, color='#e71d36', linewidth=3, label='Hysteresis (10% Buffer)')

# Plot Buffer Regions
for i in range(len(df_hist)-1):
    d1 = df_hist.index[i]
    d2 = df_hist.index[i+1]
    reg = df_hist.iloc[i]['Regime_Hyst']
    color = '#00d4ff' if reg == 'Top 200' else '#6bcb77'
    ax.axvspan(d1, d2, color=color, alpha=0.1)

ax.set_title("Alignment Switching with Hysteresis (10% Buffer)", color='white', fontsize=16)
ax.tick_params(colors='white')
ax.grid(True, color='#222222')
ax.legend(facecolor='#1a1a2e', labelcolor='white')

out_path = repo_root / "alignment_hysteresis_switcher.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved analysis plot to: {out_path}")
plt.show()
