
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler

def generate_comprehensive_excel(target_dates):
    repo_root = Path(__file__).parent
    dh = DataHandler(repo_root / "database/price_data.parquet")
    dh.load_data()
    dh.load_benchmarks(repo_root / "benchmarks")
    all_dates = dh.get_all_dates()

    sheets = {}

    for date_str in target_dates:
        target_date = pd.Timestamp(date_str)
        sheet_name = target_date.strftime("%b_%Y")
        print(f"Processing {sheet_name}...")
        
        # 1. Dates
        calc_date = target_date - pd.Timedelta(days=7)
        valid_dates = [d for d in all_dates if d <= calc_date]
        if not valid_dates:
            print(f"  No valid data found before {calc_date}")
            continue
        actual_calc_date = max(valid_dates)
        actual_lookback_start = max([d for d in all_dates if d <= (actual_calc_date - pd.Timedelta(days=365))])
        
        # 2. RSNP (Vectorized for ALL industries)
        b_prices = dh.top_1000_bench
        b_end_s = b_prices[b_prices['date'] <= actual_calc_date]
        b_start_s = b_prices[b_prices['date'] <= actual_lookback_start]
        
        if b_end_s.empty or b_start_s.empty:
            bench_return = 0.0
        else:
            bench_return = (b_end_s['index_value'].iloc[-1] / b_start_s['index_value'].iloc[-1]) - 1

        def get_robust_map(t_date):
            window = [d for d in all_dates if d <= t_date][-30:]
            subset = dh.price_df[dh.price_df['date'].isin(window)]
            return subset.sort_values('date').groupby('isin')['close'].last().to_dict()

        p_end_map = get_robust_map(actual_calc_date)
        p_start_map = get_robust_map(actual_lookback_start)

        # 3. Shareholder Data Setup
        if dh.shareholding_df is None: continue
        
        # --- A. Original (Point-to-Point) ---
        sh_trend = dh.get_shareholder_trend(target_date, lookback_quarters=4)
        # Note: get_shareholder_trend already computes 'decreased' boolean based on Point-to-Point
        if sh_trend.empty:
            print("  No shareholder data.")
            continue
            
        sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
        sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
        
        # Group Scores (Original)
        grp_orig = sh_trend.groupby('group')['decreased'].mean().to_dict()
        # Industry Scores (Original)
        ind_orig = sh_trend.groupby('industry')['decreased'].mean().to_dict()

        # --- B. Sequential (4-Quarter Drop) ---
        # Helper to get sequence
        def get_quarter_code(d):
            y = d.year
            m = d.month
            if m >= 2 and m < 5: return f"Dec-{y-1}"
            elif m >= 5 and m < 8: return f"Mar-{y}"
            elif m >= 8 and m < 11: return f"Jun-{y}"
            else: return f"Sep-{y}"
            
        curr_q = get_quarter_code(target_date)
        quarters = ["Mar", "Jun", "Sep", "Dec"]
        
        def get_prev_q(q_code, n=1):
            parts = q_code.split('-')
            code = parts[0]
            year = int(parts[1])
            if code == "Mar": idx = 0
            elif code == "Jun": idx = 1
            elif code == "Sep": idx = 2
            else: idx = 3
            linear = (year * 4) + idx
            prev_linear = linear - n
            p_year = prev_linear // 4
            p_idx = prev_linear % 4
            return f"{quarters[p_idx]}-{p_year}"
            
        qs = [curr_q, get_prev_q(curr_q, 1), get_prev_q(curr_q, 2), get_prev_q(curr_q, 3), get_prev_q(curr_q, 4)]
        
        sh_subset = dh.shareholding_df[dh.shareholding_df['quarter'].isin(qs)][['isin', 'quarter', 'total_shareholders']]
        pivot = sh_subset.pivot(index='isin', columns='quarter', values='total_shareholders')
        # Reindex to ensure all cols exist (fill NaN)
        pivot = pivot.reindex(columns=qs) 
        
        # calculate sequential drops
        d1 = pivot[qs[3]] < pivot[qs[4]] # Q4>Q3
        d2 = pivot[qs[2]] < pivot[qs[3]] # Q3>Q2
        d3 = pivot[qs[1]] < pivot[qs[2]] # Q2>Q1
        d4 = pivot[qs[0]] < pivot[qs[1]] # Q1>Q0
        
        seq_mask = d1 & d2 & d3 & d4
        seq_df = pd.DataFrame(seq_mask, columns=['is_seq']).reset_index()
        seq_df['group'] = seq_df['isin'].map(dh.isin_to_group)
        seq_df['industry'] = seq_df['isin'].map(dh.isin_to_industry)
        
        # Group Scores (Sequential)
        grp_seq = seq_df.groupby('group')['is_seq'].mean().to_dict()
        # Industry Scores (Sequential)
        ind_seq = seq_df.groupby('industry')['is_seq'].mean().to_dict()

        # 4. Compile Comprehensive List
        # Get list of all industries
        all_industries = sorted(list(set(sh_trend['industry'].dropna().unique())))
        
        rows = []
        for ind in all_industries:
            # Map Group
            # Find a representative ISIN for this industry to get group
            rep_isin = next((i for i, name in dh.isin_to_industry.items() if name == ind), None)
            grp = dh.isin_to_group.get(rep_isin, "Unknown")
            
            # Scores
            sc_ind_orig = ind_orig.get(ind, 0.0)
            sc_grp_orig = grp_orig.get(grp, 0.0)
            sc_ind_seq = ind_seq.get(ind, 0.0)
            sc_grp_seq = grp_seq.get(grp, 0.0)
            
            # RSNP
            ind_isins = [i for i, name in dh.isin_to_industry.items() if name == ind]
            wins = 0
            eligible = 0
            for isin in ind_isins:
                p1 = p_end_map.get(isin)
                p0 = p_start_map.get(isin)
                if p1 and p0 and p0 > 0:
                    eligible += 1
                    if (p1/p0 - 1) > bench_return:
                        wins += 1
            rsnp = wins/eligible if eligible > 0 else 0.0
            
            rows.append({
                "Group": grp,
                "Industry": ind,
                "Orig Grp Score": sc_grp_orig,
                "Orig Ind Score": sc_ind_orig,
                "Seq Grp Score": sc_grp_seq,
                "Seq Ind Score": sc_ind_seq,
                "RSNP": rsnp
            })
            
        df = pd.DataFrame(rows)
        # Sort by Original Ind Score desc
        df = df.sort_values("Orig Ind Score", ascending=False)
        sheets[sheet_name] = df

    # Save
    output_path = repo_root / "outputs/comprehensive_industry_scores.xlsx"
    print(f"\nSaving to {output_path}...")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                length = max(len(str(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

    print("Comprehensive Excel generation complete.")

if __name__ == "__main__":
    dates = [
        "2020-02-15",
        "2020-05-15",
        "2024-02-15",
        "2024-11-15",
        "2025-02-15",
        "2026-02-15"
    ]
    generate_comprehensive_excel(dates)
