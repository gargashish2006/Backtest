"""
NSE XBRL Shareholding Pattern Downloader - Research Script

This script explores how to download XBRL shareholding pattern files from NSE.

Based on findings:
1. NSE publishes XBRL files for regulatory filings
2. corporate-announcements API has hasXbrl flag
3. XBRL files are at nsearchives.nseindia.com
4. Need to identify correct announcement types for shareholding patterns
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time


class NSEXBRLExplorer:
    """Explore NSE XBRL file structure for shareholding patterns."""
    
    BASE_URL = "https://www.nseindia.com"
    ARCHIVE_URL = "https://nsearchives.nseindia.com"
    
    def __init__(self, verbose: bool = False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, */*',
            'Referer': 'https://www.nseindia.com/',
            'X-Requested-With': 'XMLHttpRequest',
        })
        self.verbose = verbose
        self._init_session()
    
    def _init_session(self):
        """Initialize session with cookies."""
        try:
            self.session.get(self.BASE_URL, timeout=10)
            if self.verbose:
                print("✓ Session initialized")
        except Exception as e:
            if self.verbose:
                print(f"⚠ Session init warning: {e}")
    
    def get_announcements(self, symbol: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """Get all corporate announcements for a symbol."""
        url = f"{self.BASE_URL}/api/corporate-announcements"
        params = {
            'symbol': symbol,
            'index': 'equities',
            'from_date': from_date,
            'to_date': to_date
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching announcements: {e}")
            return []
    
    def find_shareholding_patterns(self, symbol: str, years_back: int = 3) -> List[Dict[str, Any]]:
        """Find shareholding pattern filings for a symbol."""
        to_date = datetime.now()
        from_date = to_date - timedelta(days=years_back*365)
        
        from_str = from_date.strftime('%d-%m-%Y')
        to_str = to_date.strftime('%d-%m-%Y')
        
        print(f"Searching announcements for {symbol} from {from_str} to {to_str}...")
        
        announcements = self.get_announcements(symbol, from_str, to_str)
        print(f"Total announcements: {len(announcements)}")
        
        # Search for shareholding patterns
        # Common description patterns:
        # - "Shareholding Pattern"
        # - "SHHP" (abbreviation)
        # - Sometimes just in attachment text
        
        patterns = []
        
        for item in announcements:
            desc = item.get('desc', '').lower()
            att_text = item.get('attchmntText', '').lower()
            att_file = item.get('attchmntFile', '')
            has_xbrl = item.get('hasXbrl', False)
            
            # Check if this is a shareholding pattern filing
            is_pattern = False
            
            # Method 1: Check description
            if any(kw in desc for kw in ['shareholding pattern', 'shhp', 'reg 31', 'regulation 31']):
                is_pattern = True
            
            # Method 2: Check attachment text
            if 'shareholding pattern' in att_text:
                is_pattern = True
            
            # Method 3: Check file name
            if 'shhp' in att_file.lower() or 'shareholding' in att_file.lower():
                is_pattern = True
            
            if is_pattern:
                patterns.append({
                    'symbol': item.get('symbol'),
                    'date': item.get('an_dt'),
                    'description': item.get('desc'),
                    'pdf_file': att_file,
                    'xbrl_file': att_file.replace('.pdf', '.xml') if att_file.endswith('.pdf') else None,
                    'has_xbrl': has_xbrl,
                    'attachment_text': item.get('attchmntText', '')[:100],
                    'raw': item
                })
        
        return patterns
    
    def download_xbrl_file(self, xbrl_url: str, output_path: str) -> bool:
        """Download an XBRL file."""
        try:
            resp = self.session.get(xbrl_url, timeout=15)
            resp.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            
            return True
        except Exception as e:
            print(f"Error downloading {xbrl_url}: {e}")
            return False
    
    def test_xbrl_download(self, xbrl_url: str) -> Dict[str, Any]:
        """Test if an XBRL file exists and is accessible."""
        try:
            resp = self.session.head(xbrl_url, timeout=10)
            
            result = {
                'url': xbrl_url,
                'status': resp.status_code,
                'exists': resp.status_code == 200,
                'content_type': resp.headers.get('Content-Type'),
                'content_length': resp.headers.get('Content-Length'),
            }
            
            # If exists, try to get first few bytes
            if result['exists']:
                resp = self.session.get(xbrl_url, timeout=10, stream=True)
                content_start = next(resp.iter_content(1024), b'').decode('utf-8', errors='ignore')
                result['is_xml'] = content_start.strip().startswith('<?xml')
                result['preview'] = content_start[:200]
            
            return result
        except Exception as e:
            return {
                'url': xbrl_url,
                'status': 0,
                'exists': False,
                'error': str(e)
            }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Explore NSE XBRL shareholding patterns")
    parser.add_argument('--symbol', default='RELIANCE', help='Stock symbol')
    parser.add_argument('--years', type=int, default=3, help='Years of history')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--test-download', action='store_true', help='Test downloading XBRL files')
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  NSE XBRL Shareholding Pattern Explorer                         ║
║  Symbol: {args.symbol:50s}      ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    explorer = NSEXBRLExplorer(verbose=args.verbose)
    
    # Find shareholding patterns
    patterns = explorer.find_shareholding_patterns(args.symbol, args.years)
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Found {len(patterns)} shareholding pattern filings")
    
    if patterns:
        print("\nMost recent filings:")
        for i, p in enumerate(patterns[:5]):
            print(f"\n{i+1}. Date: {p['date']}")
            print(f"   Description: {p['description']}")
            print(f"   PDF: {p['pdf_file']}")
            print(f"   XBRL: {p['xbrl_file']}")
            print(f"   Has XBRL flag: {p['has_xbrl']}")
            
            if args.test_download and p['xbrl_file']:
                print(f"   Testing XBRL download...")
                result = explorer.test_xbrl_download(p['xbrl_file'])
                if result['exists']:
                    print(f"   ✅ XBRL file exists!")
                    print(f"      Content-Type: {result.get('content_type')}")
                    print(f"      Size: {result.get('content_length')} bytes")
                    print(f"      Is XML: {result.get('is_xml')}")
                else:
                    print(f"   ❌ XBRL file not found (status: {result['status']})")
    
    # Save results
    output_file = f"nse_xbrl_patterns_{args.symbol}_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(patterns, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Recommendations
    print(f"\n{'='*70}")
    print("NEXT STEPS")
    print(f"{'='*70}")
    
    if not patterns:
        print("""
❌ No shareholding pattern filings found!

Possible reasons:
1. Symbol might not be filing in this format
2. Search terms might be different
3. Filings might be under different announcement category

Try:
- Checking NSE website manually for this company
- Looking at raw announcements data
- Using different search keywords
        """)
    else:
        print(f"""
✅ Found {len(patterns)} shareholding pattern filings

If XBRL files are accessible:
1. Download XBRL files for all companies
2. Parse XBRL to extract:
   - Promoter holding %
   - FII/DII holding %
   - Public holding %
   - Number of shareholders
3. Build database of shareholding data

If XBRL files NOT accessible:
1. Download PDF files instead
2. Parse PDFs using pdfplumber/camelot
3. Extract table data
        """)


if __name__ == '__main__':
    main()
