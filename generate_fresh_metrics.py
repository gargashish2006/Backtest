import pandas as pd
from pathlib import Path
import os

def generate_comprehensive_metrics():
    # Paths
    base_path = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    db_path = base_path / "database"
    bench_path = base_path / "benchmarks"
    output_path = base_path / "outputs" / "comprehensive_metrics_feb_2026.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load Mappings
    industry_info_path = db_path / "industry_info.parquet"
    industry_df = pd.read_parquet(industry_info_path)
    isin_to_ind = dict(zip(industry_df['isin'], industry_df['industry']))
    isin_to_group = dict(zip(industry_df['isin'], industry_df['industry_group']))
    isin_to_name = dict(zip(industry_df['isin'], industry_df['company_name']))

    # 2. Load Price Data
    price_df = pd.read_parquet(db_path / "price_data.parquet")
    price_df['date'] = pd.to_datetime(price_df['date'])
    
    # 3. Dates
    end_date = pd.Timestamp("2026-02-05")
    start_date = end_date - pd.Timedelta(days=365)
    all_trading_dates = sorted(price_df['date'].unique())
    actual_end = max([d for d in all_trading_dates if d <= end_date])
    actual_start = max([d for d in all_trading_dates if d <= start_date])
    
    # 4. Top 1000 Benchmark Return
    top_1000_bench = pd.read_parquet(bench_path / "Benchmark_1000_equalWeight.parquet")
    top_1000_bench['date'] = pd.to_datetime(top_1000_bench['date'])
    b_val_end = top_1000_bench[top_1000_bench['date'] <= actual_end]['index_value'].iloc[-1]
    b_val_start = top_1000_bench[top_1000_bench['date'] <= actual_start]['index_value'].iloc[-1]
    top_1000_return = (b_val_end / b_val_start) - 1

    # 5. Shareholding Trend (Dec-25 vs Dec-24)
    sh_path = db_path / "shareholding_patterns.parquet"
    sh_df = pd.read_parquet(sh_path)
    curr_q = "Dec-2025"
    prev_q = "Dec-2024"
    sh_curr = sh_df[sh_df['quarter'] == curr_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'sh_end'})
    sh_prev = sh_df[sh_df['quarter'] == prev_q][['isin', 'total_shareholders']].rename(columns={'total_shareholders': 'sh_start'})
    sh_merged = pd.merge(sh_curr, sh_prev, on='isin', how='inner')
    sh_merged['sh_decreased'] = sh_merged['sh_end'] < sh_merged['sh_start']

    # 6. Individual Stock returns and RSNP flag
    # Robust price lookup (30 day window)
    def get_robust_prices(target_date, days=30):
        target_dates = [d for d in all_trading_dates if d <= target_date][-days:]
        subset = price_df[price_df['date'].isin(target_dates)]
        # Get last available price for each ISIN in the window
        return subset.sort_values('date').groupby('isin')['close'].last().to_dict()

    p_end_map = get_robust_prices(actual_end)
    p_start_map = get_robust_prices(actual_start)
    
    all_isins = list(isin_to_ind.keys())
    stock_data = []
    for isin in all_isins:
        p1 = p_end_map.get(isin)
        p0 = p_start_map.get(isin)
        if p1 and p0 and p0 > 0:
            ret = (p1 / p0) - 1
            beats_bench = ret > top_1000_return
            stock_data.append({
                'isin': isin,
                'industry': isin_to_ind[isin],
                'group': isin_to_group[isin],
                'is_winner': beats_bench,
                'active': True
            })
    
    stock_df = pd.DataFrame(stock_data)
    
    # 7. Aggregate Metrics
    # i) RSNP & Stock Counts
    ind_rsnp = stock_df.groupby('industry')['is_winner'].agg(['mean', 'count']).reset_index()
    group_rsnp = stock_df.groupby('group')['is_winner'].agg(['mean', 'count']).reset_index()
    
    # ii) Shareholding %
    sh_merged['industry'] = sh_merged['isin'].map(isin_to_ind)
    sh_merged['group'] = sh_merged['isin'].map(isin_to_group)
    ind_sh = sh_merged.groupby('industry')['sh_decreased'].agg(['mean', 'count']).reset_index()
    group_sh = sh_merged.groupby('group')['sh_decreased'].agg(['mean', 'count']).reset_index()

    # 8. Benchmark Returns
    def get_bench_return(folder_path, actual_end, actual_start):
        p_file = folder_path / "timeseries.parquet"
        if not p_file.exists(): return None
        df = pd.read_parquet(p_file)
        df['date'] = pd.to_datetime(df['date'])
        try:
            v1 = df[df['date'] <= actual_end]['index_value'].iloc[-1]
            v0 = df[df['date'] <= actual_start]['index_value'].iloc[-1]
            return (v1 / v0) - 1
        except:
            return None

    # Industry Benchmarks Mapping
    # Helper to match name to folder
    ind_bench_dir = bench_path / "industries"
    ind_bench_returns = {}
    
    def match_name_to_folder(name, base_dir):
        # The benchmark creator used: name.replace(' ', '_').replace('&', '_').replace('/', '__').replace('(', '_').replace(')', '_').replace('-', '_')
        # BUT many folders actually have & (as seen in ls -F)
        # Strategy: try most common transformations
        slugs = [
            name.replace(" ", "_"),
            name.replace(" ", "_").replace("&", "_"),
            name.replace(" ", "_").replace("/", "__"),
            name.replace(" ", "_").replace("/", "__").replace("&", "_"),
            name.replace(" ", "_").replace("&", "_").replace("-", "_").replace("/", "__").replace("(", "_").replace(")", "_"),
            name.replace("/", "__").replace(" ", "_").replace("&", "_")
        ]
        for s in slugs:
            path = base_dir / s
            if path.exists(): return path
        # Final fallback: case-insensitive check of all folders
        if base_dir.exists():
            for folder in os.listdir(base_dir):
                if folder.lower().replace("_", "") == name.lower().replace(" ", "").replace("&", "").replace("/", "").replace("-", "").replace("(", "").replace(")", ""):
                    return base_dir / folder
        return None

    print("Calculating Industry Benchmark returns...")
    all_industries = sorted(list(set(isin_to_ind.values())))
    for ind in all_industries:
        folder_path = match_name_to_folder(ind, ind_bench_dir)
        if folder_path:
            ret = get_bench_return(folder_path, actual_end, actual_start)
            if ret is not None:
                ind_bench_returns[ind] = ret

    print("Calculating Industry Group Benchmark returns...")
    all_groups = sorted(list(set(isin_to_group.values())))
    group_bench_returns = {}
    group_bench_dir = bench_path / "industry_groups"
    for gp in all_groups:
        folder_path = match_name_to_folder(gp, group_bench_dir)
        if folder_path:
            ret = get_bench_return(folder_path, actual_end, actual_start)
            if ret is not None:
                group_bench_returns[gp] = ret

    # 9. Combine and Finalize
    # Industry Table (Keep 'sh_decrease_pct' as well)
    ind_final = pd.merge(ind_sh.rename(columns={'mean': 'sh_decrease_pct', 'count': 'sh_stock_count'}),
                         ind_rsnp.rename(columns={'mean': 'rsnp_score', 'count': 'active_stock_count'}),
                         on='industry', how='outer')
    ind_final['benchmark_return_1y'] = ind_final['industry'].map(ind_bench_returns)
    ind_final = ind_final[['industry', 'sh_stock_count', 'sh_decrease_pct', 'benchmark_return_1y', 'active_stock_count', 'rsnp_score']]
    
    # Group Table
    group_final = pd.merge(group_sh.rename(columns={'mean': 'sh_decrease_pct', 'count': 'sh_stock_count'}),
                           group_rsnp.rename(columns={'mean': 'rsnp_score', 'count': 'active_stock_count'}),
                           on='group', how='outer')
    group_final['benchmark_return_1y'] = group_final['group'].map(group_bench_returns)
    group_final = group_final[['group', 'sh_stock_count', 'sh_decrease_pct', 'benchmark_return_1y', 'active_stock_count', 'rsnp_score']]

    # 10. Export to Excel
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        ind_final.to_excel(writer, sheet_name='Industry_Metrics', index=False)
        group_final.to_excel(writer, sheet_name='Industry_Group_Metrics', index=False)
        
    print(f"Metrics generated and saved to {output_path}")

if __name__ == "__main__":
    generate_comprehensive_metrics()
