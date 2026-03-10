#!/usr/bin/env python3
"""
Create a consolidated shareholding file by merging BSE and NSE data.

Uses shp_stocks.csv as the base to map stocks across exchanges via ISIN.
Combines quarter-wise data for Total Shareholders and Total Outstanding Shares.
"""

import os
import sys
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))


class ShareholdingConsolidator:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.shp_stocks_path = os.path.join(self.base_path, "shp_stocks.csv")
        self.bse_data_path = os.path.join(self.base_path, "bse_shareholding_patterns_deduped.csv")
        self.nse_data_path = os.path.join(self.base_path, "nse_shareholding_patterns_deduped.csv")
        self.output_path = os.path.join(self.base_path, "consolidated_shareholding_patterns.csv")

    def load_master_list(self):
        """Load shp_stocks.csv as the master mapping."""
        print("Loading master stock list from shp_stocks.csv...")
        df = pd.read_csv(self.shp_stocks_path, dtype={'BSE Code': str, 'NSE Code': str})
        
        # Standardize column names
        df.columns = df.columns.str.strip()
        
        # Clean BSE codes - remove .0 if present
        df['BSE Code'] = df['BSE Code'].apply(lambda x: x.split('.')[0] if pd.notna(x) and '.' in str(x) else x)
        
        print(f"Loaded {len(df)} stocks from master list")
        print(f"Columns: {df.columns.tolist()}")
        
        return df

    def load_bse_data(self):
        """Load BSE shareholding data."""
        print("\nLoading BSE shareholding data...")
        df = pd.read_csv(self.bse_data_path)
        
        print(f"Loaded {len(df)} BSE records")
        print(f"Unique BSE stocks: {df['symbol'].nunique()}")
        
        # Standardize date format
        df['quarter'] = pd.to_datetime(df['period'], format='%B %Y', errors='coerce')
        
        return df

    def load_nse_data(self):
        """Load NSE shareholding data."""
        print("\nLoading NSE shareholding data...")
        df = pd.read_csv(self.nse_data_path)
        
        print(f"Loaded {len(df)} NSE records")
        print(f"Unique NSE stocks: {df['symbol'].nunique()}")
        
        # Standardize date format
        df['quarter'] = pd.to_datetime(df['filing_date'], format='%d-%b-%Y', errors='coerce')
        
        return df

    def parse_quarter(self, date):
        """Convert date to quarter format (e.g., 'Dec-2025', 'Mar-2024')."""
        if pd.isna(date):
            return None
        
        # Get quarter-end month
        if date.month in [1, 2, 3]:
            qtr_month = 'Mar'
        elif date.month in [4, 5, 6]:
            qtr_month = 'Jun'
        elif date.month in [7, 8, 9]:
            qtr_month = 'Sep'
        else:
            qtr_month = 'Dec'
        
        return f"{qtr_month}-{date.year}"

    def consolidate(self):
        """Main consolidation logic."""
        
        # Load all data
        master = self.load_master_list()
        bse_data = self.load_bse_data()
        nse_data = self.load_nse_data()
        
        print("\n" + "="*70)
        print("Starting Consolidation Process")
        print("="*70)
        
        # Add quarter column
        bse_data['quarter_str'] = bse_data['quarter'].apply(self.parse_quarter)
        nse_data['quarter_str'] = nse_data['quarter'].apply(self.parse_quarter)
        
        # Create mapping dictionaries
        # BSE: symbol -> data by quarter
        bse_dict = {}
        for _, row in bse_data.iterrows():
            symbol = str(row['symbol'])
            quarter = row['quarter_str']
            if pd.isna(quarter):
                continue
            
            if symbol not in bse_dict:
                bse_dict[symbol] = {}
            
            bse_dict[symbol][quarter] = {
                'bse_total_shareholders': row['total_shareholders'],
                'bse_total_shares': row['total_shares'],
                'bse_promoter_pct': row['promoter_pct'],
                'bse_public_pct': row['public_pct'],
                'bse_fii_pct': row['fii_pct'],
                'bse_dii_pct': row['dii_pct']
            }
        
        # NSE: symbol -> data by quarter
        nse_dict = {}
        for _, row in nse_data.iterrows():
            symbol = str(row['symbol'])
            quarter = row['quarter_str']
            if pd.isna(quarter):
                continue
            
            if symbol not in nse_dict:
                nse_dict[symbol] = {}
            
            nse_dict[symbol][quarter] = {
                'nse_total_shareholders': row['total_shareholders'],
                'nse_total_shares': row['total_shares'],
                'nse_promoter_pct': row['promoter_pct'],
                'nse_public_pct': row['public_pct'],
                'nse_fii_pct': row['fii_pct'],
                'nse_dii_pct': row['dii_pct']
            }
        
        # Get all unique quarters from both datasets
        all_quarters = set()
        for stock_data in bse_dict.values():
            all_quarters.update(stock_data.keys())
        for stock_data in nse_dict.values():
            all_quarters.update(stock_data.keys())
        all_quarters = sorted([q for q in all_quarters if q])
        
        print(f"\nFound {len(all_quarters)} unique quarters across both exchanges")
        print(f"Quarter range: {all_quarters[0] if all_quarters else 'N/A'} to {all_quarters[-1] if all_quarters else 'N/A'}")
        
        # Build consolidated records
        consolidated = []
        stocks_with_data = 0
        stocks_without_data = 0
        
        for _, stock in master.iterrows():
            isin = stock.get('ISIN Code')
            bse_code = str(stock.get('BSE Code')) if pd.notna(stock.get('BSE Code')) else None
            nse_symbol = str(stock.get('NSE Code')) if pd.notna(stock.get('NSE Code')) else None
            company_name = stock.get('Name')
            
            # Check if we have any data for this stock
            has_bse_data = bse_code in bse_dict if bse_code else False
            has_nse_data = nse_symbol in nse_dict if nse_symbol else False
            
            if not has_bse_data and not has_nse_data:
                stocks_without_data += 1
                continue
            
            stocks_with_data += 1
            
            # Create a record for each quarter
            for quarter in all_quarters:
                bse_q_data = bse_dict.get(bse_code, {}).get(quarter, {}) if bse_code else {}
                nse_q_data = nse_dict.get(nse_symbol, {}).get(quarter, {}) if nse_symbol else {}
                
                # Skip if no data for this quarter
                if not bse_q_data and not nse_q_data:
                    continue
                
                # Prioritize BSE data, fallback to NSE
                # Determine data source
                data_source = ''
                if bse_q_data and nse_q_data:
                    data_source = 'BSE'  # Use BSE when both available
                    source_data = bse_q_data
                elif bse_q_data:
                    data_source = 'BSE'
                    source_data = bse_q_data
                else:
                    data_source = 'NSE'
                    source_data = nse_q_data
                
                record = {
                    'isin': isin,
                    'company_name': company_name,
                    'bse_code': bse_code if bse_code else '',
                    'nse_symbol': nse_symbol if nse_symbol else '',
                    'quarter': quarter,
                    'data_source': data_source,
                    
                    # Consolidated Data (BSE prioritized)
                    'total_shareholders': source_data.get(f'{data_source.lower()}_total_shareholders', ''),
                    'total_shares': source_data.get(f'{data_source.lower()}_total_shares', ''),
                    'promoter_pct': source_data.get(f'{data_source.lower()}_promoter_pct', ''),
                    'public_pct': source_data.get(f'{data_source.lower()}_public_pct', ''),
                    'fii_pct': source_data.get(f'{data_source.lower()}_fii_pct', ''),
                    'dii_pct': source_data.get(f'{data_source.lower()}_dii_pct', ''),
                }
                
                consolidated.append(record)
        
        # Convert to DataFrame
        df_consolidated = pd.DataFrame(consolidated)
        
        # Sort by ISIN and quarter (descending - newest first)
        df_consolidated['quarter_date'] = pd.to_datetime(df_consolidated['quarter'], format='%b-%Y')
        df_consolidated = df_consolidated.sort_values(['isin', 'quarter_date'], ascending=[True, False])
        df_consolidated = df_consolidated.drop('quarter_date', axis=1)
        
        print(f"\n" + "="*70)
        print("Consolidation Statistics")
        print("="*70)
        print(f"Total stocks in master list: {len(master)}")
        print(f"Stocks with shareholding data: {stocks_with_data}")
        print(f"Stocks without shareholding data: {stocks_without_data}")
        print(f"Total consolidated records: {len(df_consolidated)}")
        print(f"Unique ISINs with data: {df_consolidated['isin'].nunique()}")
        
        # Save to CSV
        df_consolidated.to_csv(self.output_path, index=False)
        print(f"\n✅ Consolidated file saved to: {self.output_path}")
        
        # Summary statistics
        print(f"\n" + "="*70)
        print("Data Coverage Summary")
        print("="*70)
        
        bse_records = len(df_consolidated[df_consolidated['data_source'] == 'BSE'])
        nse_records = len(df_consolidated[df_consolidated['data_source'] == 'NSE'])
        
        print(f"Records with BSE data used: {bse_records}")
        print(f"Records with NSE data used: {nse_records}")
        print(f"Total records: {len(df_consolidated)}")


def main():
    consolidator = ShareholdingConsolidator()
    consolidator.consolidate()


if __name__ == "__main__":
    main()
