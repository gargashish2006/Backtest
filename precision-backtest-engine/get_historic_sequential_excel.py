
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_sequential_excel(target_dates):
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()

    # Dictionary to store DataFrames for each sheet
    sheets = {}

    for date_str in target_dates:
        target_date = pd.Timestamp(date_str)
        sheet_name = target_date.strftime("%b_%Y")
        print(f"Processing {sheet_name} (Sequential)...")
        
        # 1. Calculation dates
        calc_date = target_date - pd.Timedelta(days=7)
        valid_dates = [d for d in all_dates if d <= calc_date]
        if not valid_dates:
            print(f"  No valid data found before {calc_date}")
            continue
            
        actual_calc_date = max(valid_dates)
        
        # 2. Sequential Shareholder Trends
        # We need data for Q0, Q1, Q2, Q3, Q4 to check 4 drops:
        # Q4->Q3, Q3->Q2, Q2->Q1, Q1->Q0
        
        if dh.shareholding_df is None:
            print("  No shareholder data found.")
            continue
            
        # Helper to get quarter code from date
        def get_quarter_code(d):
            y = d.year
            m = d.month
            if m >= 2 and m < 5: return f"Dec-{y-1}"
            elif m >= 5 and m < 8: return f"Mar-{y}"
            elif m >= 8 and m < 11: return f"Jun-{y}"
            else: return f"Sep-{y}"
            
        curr_q_code = get_quarter_code(target_date)
        
        # We need to find the sequence of 5 codes
        quarters = ["Mar", "Jun", "Sep", "Dec"]
        
        def get_prev_q(q_code, n=1):
            parts = q_code.split('-')
            code = parts[0]
            year = int(parts[1])
            
            # Map to linear
            if code == "Mar": idx = 0
            elif code == "Jun": idx = 1
            elif code == "Sep": idx = 2
            else: idx = 3
            
            linear = (year * 4) + idx
            prev_linear = linear - n
            
            p_year = prev_linear // 4
            p_idx = prev_linear % 4
            return f"{quarters[p_idx]}-{p_year}"
            
        q0 = curr_q_code
        q1 = get_prev_q(q0, 1)
        q2 = get_prev_q(q0, 2)
        q3 = get_prev_q(q0, 3)
        q4 = get_prev_q(q0, 4)
        
        required_qs = [q0, q1, q2, q3, q4]
        
        # optimize: get pivots
        sh_subset = dh.shareholding_df[dh.shareholding_df['quarter'].isin(required_qs)][['isin', 'quarter', 'total_shareholders']]
        pivot = sh_subset.pivot(index='isin', columns='quarter', values='total_shareholders')
        
        # Reorder columns to ensure strictly 4,3,2,1,0 order
        # Pivot columns might be missing some quarters if data is missing, we need to reindex
        pivot = pivot.reindex(columns=required_qs)
        
        # Logic: 
        # Drop 1: Q1 < Q2
        # Drop 2: Q2 < Q3
        # Drop 3: Q3 < Q4
        # Drop 4: Q0 < Q1 ? OR is it just 4 sequential drops?
        # User said "quarter on quarter sequential". Usually means verifying strict decline chain.
        
        # Let's count how many sequential drops.
        # But for *Selection*, if we enforce 4/4 it might be too strict.
        # Let's define "Sequential Score" as the number of sequential drops.
        # And define "Decreased" boolean for aggregation as "Strictly Decreased in ALL 4 steps"? 
        # Or maybe "At least 3 steps"?
        # Given "Rejected" implementation, let's assume strict 4-step decline was the intention of "Sequential Comparison".
        
        # Check drops
        # Q4 -> Q3
        d1 = pivot[q3] < pivot[q4]
        # Q3 -> Q2
        d2 = pivot[q2] < pivot[q3]
        # Q2 -> Q1
        d3 = pivot[q1] < pivot[q2]
        # Q1 -> Q0
        d4 = pivot[q0] < pivot[q1]
        
        # "Sequential Decrease" = True if ALL 4 are True?
        # Let's try strict.
        is_sequential = d1 & d2 & d3 & d4
        
        # Make a DF with this boolean
        sh_trend = pd.DataFrame(is_sequential, columns=['sequential_decrease']).reset_index()
        # Filter only those with data (if any checks resulted in False due to NaN, they are False)
        # NaN comparisons usually return False in pandas unless specified.
        
        sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
        
        # (i) Group Scores
        group_stats = sh_trend.groupby('group')['sequential_decrease'].agg(['mean', 'count']).reset_index()
        group_stats = group_stats[group_stats['count'] >= 5]
        group_stats = group_stats.sort_values('mean', ascending=False)
        
        if group_stats.empty:
            print("  No valid groups found.")
            continue

        # Filter Top 50% Groups
        num_to_pick = max(1, int(len(group_stats) * 0.50))
        top_groups = group_stats.head(num_to_pick)['group'].tolist()
        group_score_map = dict(zip(group_stats['group'], group_stats['mean']))

        # (ii) Industry Scores
        ind_in_groups = sh_trend[sh_trend['group'].isin(top_groups)]
        if ind_in_groups.empty:
            print("  No industries in top groups.")
            continue
            
        ind_stats = ind_in_groups.groupby('industry')['sequential_decrease'].agg(['mean', 'count']).reset_index()
        
        # Filter High Breadth Industries (>25%)
        # User requested relaxation to 25% to see more results
        qualified_inds = ind_stats[ind_stats['mean'] >= 0.25].copy()
        qualified_ind_list = qualified_inds['industry'].tolist()
        ind_score_map = dict(zip(qualified_inds['industry'], qualified_inds['mean']))
        
        if not qualified_ind_list:
            print("  No industries qualified > 50% sequential decrease.")
            # Let's try relaxing to > 30% if empty? 
            # No, user wants to see "what will be the list". If it's empty, it's empty.
            # But let's check max mean.
            max_mean = ind_stats['mean'].max()
            print(f"  Max Industry Sequential Score: {max_mean:.1%}")
            
            # Use top 10 industries regardless of threshold if none pass 50%?
            # Or just continue?
            # Let's match the Champion logic: strict 50% threshold.
            continue

        # (iii) RSNP Calculation (Same as before)
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        b_prices = dh.top_1000_bench
        b_end_s = b_prices[b_prices['date'] <= actual_calc_date]
        b_start_s = b_prices[b_prices['date'] <= actual_lookback_start]
        
        if b_end_s.empty or b_start_s.empty: continue
        bench_return = (b_end_s['index_value'].iloc[-1] / b_start_s['index_value'].iloc[-1]) - 1
        
        def get_robust_map(t_date):
            window = [d for d in all_dates if d <= t_date][-30:]
            subset = dh.price_df[dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()
        
        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)
        
        industry_rsnp = []
        for ind in qualified_ind_list:
            ind_isins = [isin for isin, name in dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            
            if eligible > 0:
                rsnp = wins/eligible
                if rsnp >= 0.40: # RSNP Threshold
                     grp = dh.isin_to_group.get(ind_isins[0], "Unknown")
                     industry_rsnp.append({
                         'Industry': ind,
                         'Group': grp,
                         'Sequential Grp Score': group_score_map.get(grp, 0),
                         'Sequential Ind Score': ind_score_map.get(ind, 0),
                         'RSNP Score': rsnp
                     })
        
        if not industry_rsnp:
            print("  No industries passed RSNP filter.")
            continue

        df = pd.DataFrame(industry_rsnp)
        df = df.sort_values('RSNP Score', ascending=False)
        sheets[sheet_name] = df

    # Save to Excel
    output_path = repo_root / "outputs/historic_sequential_selections.xlsx"
    print(f"\nSaving to {output_path}...")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                length = max(len(str(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

    print("Sequential Excel generation complete.")

if __name__ == "__main__":
    dates = [
        "2020-02-15",
        "2020-05-15",
        "2024-02-15",
        "2024-11-15",
        "2025-02-15",
        "2026-02-15"
    ]
    generate_sequential_excel(dates)
