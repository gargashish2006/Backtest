#!/usr/bin/env python
import pandas as pd
from pathlib import Path
import sys

# Handle imports
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from strategies.industry_group.Sync15_RSNP_Top1000_Large import Sync15_RSNP_Top1000_Large

def generate_production_rebalance():
    strat = Sync15_RSNP_Top1000_Large()
    strat.load_data()
    
    # REBALANCE DATE: Feb 15, 2026
    date = pd.Timestamp('2026-02-15')
    
    # 1. RUN SELECTION AND EXTRACT INTERMEDIATE METRICS
    # Replicating the logic to capture percentages
    cut = date - pd.Timedelta(days=120)
    recent = strat.shp_with_info[(strat.shp_with_info['quarter_date'] >= cut) & (strat.shp_with_info['quarter_date'] <= date)].copy()
    recent = recent.sort_values('quarter_date').groupby('isin').last().reset_index()
    
    # Group Metrics
    g_metrics = recent.groupby('industry_group').agg(tot=('isin', 'count'), dec=('decreasing', 'sum')).reset_index()
    g_metrics['group_shp_pct'] = g_metrics['dec'] / g_metrics['tot'] * 100
    
    # Industry Metrics
    i_metrics = recent.groupby('industry').agg(tot=('isin', 'count'), dec=('decreasing', 'sum'), group=('industry_group', 'first')).reset_index()
    i_metrics['ind_shp_pct'] = i_metrics['dec'] / i_metrics['tot'] * 100
    
    # RSNP Ranking
    rs_date = date - pd.Timedelta(days=strat.LAG_DAYS)
    end_bench = strat.universe_bench[strat.universe_bench['date'] <= rs_date].iloc[-1]['index_value']
    start_date_bench = rs_date - pd.Timedelta(days=strat.RS_LOOKBACK_DAYS)
    start_bench = strat.universe_bench[strat.universe_bench['date'] <= start_date_bench].iloc[-1]['index_value']
    bench_ret = (end_bench / start_bench) - 1
    
    # Run selection to get ISINs
    selected_isins = strat.calculate_selection(date)
    
    # 2. ENRICH PICKS
    name_map = dict(zip(strat.industry_df['isin'], strat.industry_df['company_name']))
    ind_map = dict(zip(strat.industry_df['isin'], strat.industry_df['industry']))
    group_map = dict(zip(strat.industry_df['isin'], strat.industry_df['industry_group']))
    
    p_slice = strat.price_df[(strat.price_df['date'] <= date) & (strat.price_df['date'] > date - pd.Timedelta(days=14))].sort_values('date').groupby('isin').last().reset_index()
    
    final_picks = []
    for isin in selected_isins:
        name = name_map.get(isin, isin)
        industry = ind_map.get(isin, 'Unknown')
        group = group_map.get(isin, 'Unknown')
        
        # Metrics
        rsnp = strat.calculate_rsnp(industry, rs_date, strat.RS_LOOKBACK_DAYS, bench_ret)
        ind_sh = i_metrics[i_metrics['industry'] == industry]['ind_shp_pct'].iloc[0] if not i_metrics[i_metrics['industry'] == industry].empty else 0
        group_sh = g_metrics[g_metrics['industry_group'] == group]['group_shp_pct'].iloc[0] if not g_metrics[g_metrics['industry_group'] == group].empty else 0
        
        price = p_slice[p_slice['isin'] == isin]['close'].iloc[0]
        mcap = price * strat.shares_map.get(isin, 0) / 10000000 
        
        final_picks.append({
            'ISIN': isin,
            'Company': name,
            'Industry': industry,
            'Grp SHP%': f"{group_sh:.1f}%",
            'Ind SHP%': f"{ind_sh:.1f}%",
            'Ind RSNP': f"{rsnp:.2f}",
            'Price': round(price, 2),
            'M-Cap(Cr)': round(mcap, 2)
        })
    
    df = pd.DataFrame(final_picks)
    
    # 3. EXPORT
    local_out = Path(project_root) / 'strategies/outputs/rebalance/aug_2025_base_large_enriched.csv'
    local_out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(local_out, index=False)
    
    f_date = date.strftime('%b_%Y').lower()
    artifact_path = f'/Users/shubhrakasana/.gemini/antigravity/brain/f5a57827-91d7-44c1-8f44-e1b548e0d947/rebalance_{f_date}_base_large_enriched.csv'
    df.to_csv(artifact_path, index=False)
    
    print("\n" + "="*110)
    print("ENRICHED PRODUCTION REBALANCE: BASE STRATEGY (SHP LARGE 1000)")
    print(f"Execution Date: {date.date()} | Signal Date: {rs_date.date()} (7-day Lag)")
    print("="*110)
    print(df.to_string(index=False))
    print("="*110)
    print(f"Total Portfolio: {len(df)} Stocks | Weight: 6.67% per stock")
    print(f"CSV saved to: {artifact_path}")

if __name__ == "__main__":
    generate_production_rebalance()
