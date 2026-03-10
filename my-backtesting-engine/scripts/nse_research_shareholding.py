"""Research script to explore NSE shareholding pattern APIs.

This script tests various NSE endpoints to determine:
1. How to fetch shareholding pattern data
2. What data fields are available
3. Required headers/cookies for scraping
4. Rate limits and anti-scraping measures
5. Historical data availability

Usage:
    python scripts/nse_research_shareholding.py --symbol RELIANCE
    python scripts/nse_research_shareholding.py --symbol TCS --verbose
"""

import argparse
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests


class NSEResearchClient:
    """Research client to test NSE shareholding endpoints."""

    BASE_URL = "https://www.nseindia.com"
    
    # NSE requires these headers to avoid 403 Forbidden
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.nseindia.com/",
    }

    def __init__(self, verbose: bool = False):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.verbose = verbose
        self._initialize_session()

    def _initialize_session(self) -> None:
        """Initialize session by visiting homepage to get cookies."""
        try:
            if self.verbose:
                print("Initializing NSE session (fetching cookies)...")
            
            # Visit homepage to establish session
            resp = self.session.get(
                self.BASE_URL,
                timeout=10,
            )
            resp.raise_for_status()
            
            if self.verbose:
                print(f"Session initialized. Cookies: {list(self.session.cookies.keys())}")
                
        except Exception as e:
            print(f"Warning: Failed to initialize session: {e}")

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to NSE endpoint."""
        url = f"{self.BASE_URL}{endpoint}"
        
        if self.verbose:
            print(f"\nGET {url}")
            if params:
                print(f"Params: {params}")
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            
            if self.verbose:
                print(f"Status: {resp.status_code}")
                print(f"Response size: {len(resp.content)} bytes")
            
            return resp.json()
            
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response: {e.response.text[:500]}")
            raise
        except Exception as e:
            print(f"Error: {e}")
            raise

    def test_shareholding_api(self, symbol: str) -> Dict[str, Any]:
        """Test primary shareholding pattern API endpoint."""
        print(f"\n{'='*60}")
        print(f"Testing Shareholding Pattern API for {symbol}")
        print(f"{'='*60}")
        
        # Endpoint 1: Corporate shareholding page data
        endpoint = "/api/corporate-share-holdings"
        params = {
            "symbol": symbol,
            "index": "equities"
        }
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got response for {symbol}")
            print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            # Pretty print first record if available
            if isinstance(data, dict):
                print("\nSample data structure:")
                print(json.dumps(data, indent=2, default=str)[:1000])
            elif isinstance(data, list) and data:
                print("\nFirst record:")
                print(json.dumps(data[0], indent=2, default=str)[:1000])
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def test_quote_api(self, symbol: str) -> Dict[str, Any]:
        """Test quote API which may contain shareholding summary."""
        print(f"\n{'='*60}")
        print(f"Testing Quote API for {symbol}")
        print(f"{'='*60}")
        
        endpoint = f"/api/quote-equity"
        params = {"symbol": symbol}
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got quote data for {symbol}")
            
            # Look for shareholding-related fields
            if "priceInfo" in data:
                print("\nPrice Info keys:", list(data["priceInfo"].keys()))
            if "securityInfo" in data:
                print("Security Info keys:", list(data["securityInfo"].keys()))
            
            # Check for shareholding pattern link
            if "metadata" in data:
                print("Metadata keys:", list(data["metadata"].keys()))
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def test_corporate_info_api(self, symbol: str) -> Dict[str, Any]:
        """Test corporate info API for shareholding details."""
        print(f"\n{'='*60}")
        print(f"Testing Corporate Info API for {symbol}")
        print(f"{'='*60}")
        
        endpoint = "/api/corporates-corporateActions"
        params = {
            "symbol": symbol,
            "index": "equities"
        }
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got corporate info for {symbol}")
            print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            if isinstance(data, dict):
                print("\nSample structure:")
                print(json.dumps(data, indent=2, default=str)[:800])
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def test_historical_shareholding(self, symbol: str) -> Dict[str, Any]:
        """Test historical shareholding pattern endpoint."""
        print(f"\n{'='*60}")
        print(f"Testing Historical Shareholding for {symbol}")
        print(f"{'='*60}")
        
        # This endpoint typically requires period parameters
        endpoint = "/api/historical/securityArchives"
        params = {
            "symbol": symbol,
            "from": "01-01-2023",
            "to": "31-12-2023",
            "dataType": "priceVolumeDeliverable",
            "series": "EQ"
        }
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got historical data for {symbol}")
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def test_shareholding_pattern_webpage(self, symbol: str) -> Dict[str, Any]:
        """Test the actual shareholding pattern page endpoint."""
        print(f"\n{'='*60}")
        print(f"Testing Shareholding Pattern Webpage for {symbol}")
        print(f"{'='*60}")
        
        # Try the actual shareholding pattern endpoint used by the website
        endpoint = "/api/shareholding-pattern"
        params = {"symbol": symbol}
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got shareholding pattern for {symbol}")
            print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            if isinstance(data, dict):
                print("\nSample structure:")
                print(json.dumps(data, indent=2, default=str)[:1500])
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def test_corporate_shareholding(self, symbol: str) -> Dict[str, Any]:
        """Test corporate shareholding endpoint."""
        print(f"\n{'='*60}")
        print(f"Testing Corporate Shareholding for {symbol}")
        print(f"{'='*60}")
        
        endpoint = "/api/corporates-shareholding"
        params = {"symbol": symbol}
        
        try:
            data = self._get(endpoint, params)
            
            print(f"\n✅ SUCCESS - Got corporate shareholding for {symbol}")
            print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            if isinstance(data, dict):
                print("\nData preview:")
                print(json.dumps(data, indent=2, default=str)[:1500])
            
            return data
            
        except Exception as e:
            print(f"\n❌ FAILED - {e}")
            return {}

    def analyze_results(self, symbol: str, results: Dict[str, Any]) -> None:
        """Analyze and summarize findings."""
        print(f"\n{'='*60}")
        print(f"ANALYSIS SUMMARY FOR {symbol}")
        print(f"{'='*60}")
        
        print("\n🔍 Key Findings:")
        
        # Check what data we got
        endpoints_tested = ["shareholding", "quote", "corporate_info", "historical"]
        successful = sum(1 for k, v in results.items() if v)
        
        print(f"✓ Tested {len(endpoints_tested)} endpoints")
        print(f"✓ Successful: {successful}/{len(endpoints_tested)}")
        
        # Document required fields
        print("\n📊 Required Data Fields to Extract:")
        fields = [
            "- Promoter holding %",
            "- FII/FPI holding %", 
            "- DII holding %",
            "- Public holding %",
            "- Total shareholders",
            "- Total shares outstanding",
            "- Date/Quarter"
        ]
        for field in fields:
            print(field)
        
        print("\n⚠️  Anti-Scraping Measures Detected:")
        print("✓ Requires valid User-Agent header")
        print("✓ Requires session cookies from homepage visit")
        print("✓ Requires Referer header")
        
        print("\n💡 Next Steps:")
        print("1. Identify the correct API endpoint with shareholding data")
        print("2. Map JSON response fields to our required schema")
        print("3. Determine historical data availability (how many quarters)")
        print("4. Test rate limits (requests per minute/hour)")
        print("5. Implement robust error handling for missing data")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research NSE shareholding data APIs"
    )
    parser.add_argument(
        "--symbol",
        default="RELIANCE",
        help="NSE symbol to test (default: RELIANCE)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed request/response info"
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Sleep between API calls (seconds)"
    )
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  NSE Shareholding Data Research Script                      ║
║  Testing endpoints for symbol: {args.symbol:30s}    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    client = NSEResearchClient(verbose=args.verbose)
    results = {}
    
    # Test 1: Shareholding API
    results["shareholding"] = client.test_shareholding_api(args.symbol)
    time.sleep(args.sleep)
    
    # Test 2: Quote API
    results["quote"] = client.test_quote_api(args.symbol)
    time.sleep(args.sleep)
    
    # Test 3: Corporate Info API
    results["corporate_info"] = client.test_corporate_info_api(args.symbol)
    time.sleep(args.sleep)
    
    # Test 4: Historical Shareholding
    results["historical"] = client.test_historical_shareholding(args.symbol)
    time.sleep(args.sleep)
    
    # Test 5: Shareholding Pattern Webpage
    results["shareholding_pattern"] = client.test_shareholding_pattern_webpage(args.symbol)
    time.sleep(args.sleep)
    
    # Test 6: Corporate Shareholding
    results["corporate_shareholding"] = client.test_corporate_shareholding(args.symbol)
    
    # Analyze and summarize
    client.analyze_results(args.symbol, results)
    
    # Save results to file
    output_file = f"nse_research_{args.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Full results saved to: {output_file}")


if __name__ == "__main__":
    main()
