import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.structural_alpha_group_strategy import StructuralAlphaGroupStrategy

def generate_production_list():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # 35% Relative, Unlimited stocks (9999), 8Q Lookback
    strategy = StructuralAlphaGroupStrategy(dh, num_stocks=9999, max_per_industry=9999, 
                                            shareholder_lookback_quarters=8, 
                                            group_top_pct=0.35)
                                            
    target_date = dh.get_all_dates()[-1]
    print(f"Generating Selection for Date: {target_date}")
    
    selection_weights = strategy.calculate_selection(target_date)
    
    if not selection_weights:
        print("No stocks selected! Check filters.")
        return

    # Extract details for the stocks
    results = []
    prices = dh.get_daily_prices(target_date)
    univ = dh.get_universe(target_date, size=1000)
    
    for isin, weight in selection_weights.items():
        price = prices.get(isin, 0)
        industry = dh.isin_to_industry.get(isin, "Unknown")
        group = dh.isin_to_group.get(isin, "Unknown")
        mc_info = univ[univ['isin'] == isin]
        mc = mc_info['mc'].values[0] if not mc_info.empty else 0
        
        results.append({
            'ISIN': isin,
            'Group': group,
            'Industry': industry,
            'MarketCap_Cr': mc,
            'CurrentPrice': price,
            'TargetWeight': weight
        })
        
    df = pd.DataFrame(results).sort_values(['Group', 'Industry', 'MarketCap_Cr'], ascending=[True, True, False])
    
    output_path = repo_root / "outputs/Final_Feb_2026_Unlimited_Rebalance.xlsx"
    df.to_excel(output_path, index=False)
    
    print(f"\nSuccessfully generated rebalance list with {len(df)} stocks.")
    print(f"File saved to: {output_path}")

if __name__ == "__main__":
    generate_production_list()
