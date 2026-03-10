from bs4 import BeautifulSoup
import re

class BSEHtmlShpParser:
    """Parses BSE Shareholding Pattern HTML files."""

    def __init__(self, html_content: str):
        self.soup = BeautifulSoup(html_content, 'html.parser')

    def parse(self):
        """Extracts key metrics."""
        summary = {
            'total_shares': 0,
            'total_shareholders': 0,
            'promoter_pct': 0.0,
            'public_pct': 0.0,
            'fii_pct': 0.0,
            'dii_pct': 0.0
        }

        # Strategy: Iterate through all rows in the document.
        # Identify rows by their first cell content or content in specific columns.
        
        rows = self.soup.find_all('tr')
        
        for row in rows:
            cols = [td.get_text().strip() for td in row.find_all('td')]
            if not cols:
                cols = [th.get_text().strip() for th in row.find_all('th')]
            
            if not cols:
                continue
                
            # Basic cleaning of cols
            # Remove empty strings from list if needed, but positional accuracy matters.
            # However, `read_webpage` output showed some empty cells.
            
            # Helper to parse percentage
            def parse_pct(s):
                try:
                    return float(s.replace('%', '').strip())
                except:
                    return 0.0
            
            # Helper to parse int
            def parse_int(s):
                try:
                    return int(s.replace(',', '').strip())
                except:
                    return 0

            first_col = cols[0]
            second_col = cols[1] if len(cols) > 1 else ""
            
            # Table I Summary Rows
            # Pattern: (A) | Promoter & ... | ... | Pct
            if first_col == '(A)' and 'Promoter' in second_col:
                # Based on observation, Total Shares is usually around col 6 or 7, Pct around 7 or 8.
                # Let's look for the percentage symbol in the row
                for i, txt in enumerate(cols):
                    if '%' in txt:
                        summary['promoter_pct'] = parse_pct(txt)
                        break
            
            elif first_col == '(B)' and 'Public' in second_col:
                for i, txt in enumerate(cols):
                    if '%' in txt:
                        summary['public_pct'] = parse_pct(txt)
                        break
                # Also try to get total shareholders and shares
                # Usually Shareholders is col 2, Total Shares col 6 (if we count 0-indexed)
                # Let's try to identify by value magnitude if possible, or position.
                # | (B) | Public | 852827 | ...
                if len(cols) > 2:
                    summary['total_shareholders'] += parse_int(cols[2]) # This is public shareholders. Promoter has separate.
            
            elif (('Total' in first_col or 'Total' in second_col) and 
                  ('A+B+C' in first_col or 'A+B+C' in second_col) and 
                  len(cols) > 5):
                 # The Grand Total row (Total (A+B+C))
                 # Scan for 100.00%
                 # But we want total shares.
                 # Usually the largest integer in the row before the 100%.
                 try:
                     # Find 100.00% index (looking for exact 100.00 or just 100)
                     idx_100 = -1
                     for i, txt in enumerate(cols):
                         if '100.00' in txt:
                             idx_100 = i
                             break
                     
                     if idx_100 > 0:
                         # The value before it is usually total shares ie. cols[idx_100-1]
                         # However, sometimes there are empty columns in between or extra columns.
                         # We look backwards from 100% for the first valid large integer.
                         found_shares = 0
                         for k in range(idx_100 - 1, -1, -1):
                             val = parse_int(cols[k])
                             if val > 1000: # Assumption: Total shares > 1000
                                 found_shares = val
                                 break
                         
                         if found_shares > 0:
                             summary['total_shares'] = found_shares
                 except: pass

            # Table III - Public Shareholding Details
            # We look for specific categories to sum up FII and DII
            
            # Categories often differ in exact text, so use keywords.
            
            # FII / FPI
            # "Foreign Portfolio Investors"
            if 'Foreign Portfolio Investors' in first_col or 'Foreign Portfolio Investors' in second_col:
                # Add to FII
                for txt in cols:
                    if '%' in txt:
                        summary['fii_pct'] += parse_pct(txt)
                        # We break because there might be multiple % columns (voting rights etc), usually shareholding is first.
                        break
            
            # Mutual Funds
            elif 'Mutual Funds' in first_col or 'Mutual Funds' in second_col:
                 for txt in cols:
                    if '%' in txt:
                        summary['dii_pct'] += parse_pct(txt)
                        break

            # Insurance Companies
            elif 'Insurance Companies' in first_col or 'Insurance Companies' in second_col:
                 for txt in cols:
                    if '%' in txt:
                        summary['dii_pct'] += parse_pct(txt)
                        break
            
            # Banks
            elif first_col == '(d)' and 'Banks' in second_col: # Sometimes 'Banks' is just Banks
                 for txt in cols:
                    if '%' in txt:
                        summary['dii_pct'] += parse_pct(txt)
                        break
            
            # Alternate Investment Funds (often considered DII)
            elif 'Alternate Investment Funds' in first_col or 'Alternate Investment Funds' in second_col:
                 for txt in cols:
                    if '%' in txt:
                        summary['dii_pct'] += parse_pct(txt)
                        break
            
            # Provident Funds/ Pension Funds
            elif 'Provident Funds' in first_col or 'Pension Funds' in second_col:
                 for txt in cols:
                    if '%' in txt:
                        summary['dii_pct'] += parse_pct(txt)
                        break
            
            # Update promoter shareholders to get total shareholders
            if first_col == '(A)' and 'Promoter' in second_col:
                if len(cols) > 2:
                    summary['total_shareholders'] += parse_int(cols[2])

        return summary
