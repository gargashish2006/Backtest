"""NSE Shareholding Pattern Data - Alternative Approaches

NSE provides shareholding pattern data through multiple channels:

1. **Company-specific page**: 
   URL: https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE
   - Navigate to "Company Information" > "Shareholding Pattern"
   - Data is typically in quarterly format

2. **Bulk downloads**:
   - NSE provides bulk CSV/Excel files for shareholding patterns
   - Available at: https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern

3. **XBRL filings**:
   - Companies file shareholding patterns in XBRL format
   - Can be parsed but requires XBRL parser

4. **Third-party APIs**:
   - BSE API (more accessible than NSE)
   - Financial data aggregators

Let's test a different approach: selenium-based scraping or checking for bulk download files.
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


class NSEShareholdingResearcher:
    """Alternative research methods for NSE shareholding data."""
    
    BASE_URL = "https://www.nseindia.com"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
    }
    
    def __init__(self, verbose: bool = False):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.verbose = verbose
        self._init_session()
    
    def _init_session(self):
        """Initialize session with cookies."""
        try:
            # Try to get the main page
            resp = self.session.get(self.BASE_URL, timeout=10)
            if self.verbose:
                print(f"Session init status: {resp.status_code}")
                print(f"Cookies: {list(self.session.cookies.keys())}")
        except Exception as e:
            if self.verbose:
                print(f"Session init warning: {e}")
    
    def test_bulk_downloads_page(self) -> Dict[str, Any]:
        """Check if there are bulk download options for shareholding data."""
        print("\n" + "="*60)
        print("Testing Bulk Downloads Page")
        print("="*60)
        
        url = f"{self.BASE_URL}/companies-listing/corporate-filings-shareholding-pattern"
        
        try:
            resp = self.session.get(url, timeout=15)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Look for download links
                links = soup.find_all('a', href=re.compile(r'\.(csv|xlsx|xls|zip)', re.I))
                
                print(f"\n✅ Found {len(links)} potential download links:")
                for link in links[:10]:  # Show first 10
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    print(f"  - {text}: {href}")
                
                return {"success": True, "links": [l.get('href') for l in links]}
            else:
                print(f"❌ Failed with status {resp.status_code}")
                return {"success": False}
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_company_info_endpoint(self, symbol: str) -> Dict[str, Any]:
        """Test the company info endpoint that might have shareholding links."""
        print("\n" + "="*60)
        print(f"Testing Company Info for {symbol}")
        print("="*60)
        
        # Try the company info API
        endpoint = "/api/quote-equity"
        params = {"symbol": symbol}
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            
            data = resp.json()
            print(f"✅ Got company info for {symbol}")
            
            # Check securityInfo for issued size (total shares)
            if "securityInfo" in data:
                issued_size = data["securityInfo"].get("issuedSize")
                print(f"  Total Shares (issuedSize): {issued_size:,}" if issued_size else "  Total Shares: Not found")
            
            # Look for any shareholding-related fields
            shareholding_keys = []
            for key in data.keys():
                if "share" in key.lower() or "hold" in key.lower():
                    shareholding_keys.append(key)
            
            if shareholding_keys:
                print(f"  Potential shareholding keys: {shareholding_keys}")
            
            return data
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {}
    
    def search_for_api_in_network(self, symbol: str) -> None:
        """
        Provide instructions for finding the actual API endpoint.
        This requires manual browser inspection.
        """
        print("\n" + "="*60)
        print("Manual API Discovery Instructions")
        print("="*60)
        
        print(f"""
To find the exact shareholding API endpoint:

1. Open Chrome/Firefox DevTools (F12)
2. Go to Network tab
3. Visit: https://www.nseindia.com/get-quotes/equity?symbol={symbol}
4. Click on "Shareholding Pattern" or "Company Information" tab
5. Look for XHR/Fetch requests in Network tab
6. Find requests containing "{symbol}" and "shareholding" or "pattern"
7. Note the endpoint URL and parameters

Common patterns to look for:
- /api/company-shareholding-pattern
- /api/equity-shareholding
- /api/chart-databyindex (might include shareholding data)
- /api/companyMaster (company details)

The actual endpoint may have changed from when this script was written.
        """)
    
    def test_bse_alternative(self, symbol: str) -> Dict[str, Any]:
        """BSE is often more accessible than NSE - test if data is available."""
        print("\n" + "="*60)
        print(f"Testing BSE Alternative for {symbol}")
        print("="*60)
        
        # BSE stock codes are different - would need mapping
        # For now, just document the approach
        print("""
BSE Shareholding Data Availability:

BSE website structure:
- URL: https://www.bseindia.com/stock-share-price/
- Shareholding pattern available in: Announcements > Shareholding Pattern
- BSE provides more accessible data download options
- Requires BSE stock code (different from NSE symbol)

Note: We would need NSE symbol to BSE code mapping.
This could be extracted from dhan_instruments.csv if it contains BSE data.
        """)
        
        return {"note": "BSE alternative documented"}


def main():
    parser = argparse.ArgumentParser(
        description="NSE Shareholding Research - Alternative Approaches"
    )
    parser.add_argument("--symbol", default="RELIANCE", help="Symbol to test")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  NSE Shareholding Data - Alternative Research               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    researcher = NSEShareholdingResearcher(verbose=args.verbose)
    
    # Test 1: Bulk downloads page
    results = {}
    results["bulk_downloads"] = researcher.test_bulk_downloads_page()
    time.sleep(2)
    
    # Test 2: Company info (get total shares)
    results["company_info"] = researcher.test_company_info_endpoint(args.symbol)
    time.sleep(2)
    
    # Test 3: Manual discovery instructions
    researcher.search_for_api_in_network(args.symbol)
    
    # Test 4: BSE alternative
    results["bse_alternative"] = researcher.test_bse_alternative(args.symbol)
    
    # Summary
    print("\n" + "="*60)
    print("RESEARCH SUMMARY")
    print("="*60)
    
    print("""
Key Findings:

1. NSE's direct shareholding API endpoints are either:
   - Moved/renamed (404 errors)
   - Require authentication we don't have
   - Behind JavaScript/SPA rendering

2. Available Data Sources:
   ✓ Total Shares Outstanding: Available via /api/quote-equity
   ? Shareholding Pattern: Need to find correct endpoint or use bulk files
   
3. Recommended Approaches:

   Option A: Manual API Discovery
   - Use browser DevTools to find the real API endpoint
   - NSE's website DOES show shareholding data, so API exists
   
   Option B: Bulk File Downloads
   - Check if NSE provides daily/weekly bulk shareholding CSV files
   - Parse and import into our database
   
   Option C: BSE Website
   - BSE may have more accessible APIs
   - Requires symbol mapping (NSE → BSE)
   
   Option D: Third-Party Data Providers
   - Commercial APIs (Alphavantage, EOD, etc.)
   - May have costs but more reliable

4. Next Steps:
   - Manually inspect NSE website to find working API
   - Check if bulk downloads are available
   - Consider BSE as primary source
   - Document actual working endpoint once found
    """)
    
    # Save results
    output_file = f"nse_research_alt_{args.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    main()
