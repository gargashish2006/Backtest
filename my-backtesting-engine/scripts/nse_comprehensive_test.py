"""Final comprehensive test of NSE endpoints for shareholding data.

This script systematically tests all known NSE API patterns to find shareholding data.
"""

import json
import time
import requests
from typing import Dict, Any, List, Tuple


def test_all_endpoints(symbol: str = "RELIANCE") -> None:
    """Test all possible NSE endpoints systematically."""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    # Initialize session
    try:
        session.get('https://www.nseindia.com', timeout=10)
        print("✓ Session initialized\n")
    except:
        print("⚠ Session init failed (may still work)\n")
    
    # All endpoints to test with variations
    test_cases: List[Tuple[str, Dict[str, Any], str]] = [
        # Quote and company info
        ('quote-equity', {'symbol': symbol}, 'Basic quote data'),
        ('quote-derivative', {'symbol': symbol}, 'Derivative quote'),
        ('quote-meta', {'symbol': symbol, 'type': 'equity'}, 'Quote metadata'),
        
        # Corporate data
        ('corporates-corporateActions', {'symbol': symbol, 'index': 'equities'}, 'Corporate actions'),
        ('corporate-announcements', {'symbol': symbol, 'index': 'equities'}, 'Announcements'),
        ('corporate-info', {'symbol': symbol}, 'Corporate info'),
        
        # Chart data (sometimes has extra info)
        ('chart-databyindex', {'index': symbol, 'indices': 'false'}, 'Chart data'),
        ('chart-databyindex', {'index': symbol, 'indices': 'true'}, 'Chart data (indices mode)'),
        
        # Company master and details
        ('company-master', {'symbol': symbol}, 'Company master'),
        ('companyMaster', {'symbol': symbol}, 'Company master (alt)'),
        ('company-info', {'symbol': symbol}, 'Company detailed info'),
        
        # Shareholding attempts
        ('shareholding-pattern', {'symbol': symbol}, 'Shareholding pattern'),
        ('shareholding', {'symbol': symbol}, 'Shareholding'),
        ('corporate-shareholding', {'symbol': symbol}, 'Corporate shareholding'),
        ('equity-shareholding', {'symbol': symbol}, 'Equity shareholding'),
        
        # Historical data
        ('historical/cm/equity', {'symbol': symbol, 'series': '["EQ"]'}, 'Historical equity'),
        
        # Market data archives
        ('marketStatus', {}, 'Market status (might have references)'),
    ]
    
    results = []
    found_shareholding = False
    
    print(f"Testing {len(test_cases)} endpoints for {symbol}\n")
    print("="*70)
    
    for endpoint, params, description in test_cases:
        url = f'https://www.nseindia.com/api/{endpoint}'
        
        try:
            resp = session.get(url, params=params, timeout=15)
            status = resp.status_code
            
            result = {
                'endpoint': endpoint,
                'params': params,
                'description': description,
                'status': status,
                'success': status == 200
            }
            
            if status == 200:
                try:
                    data = resp.json()
                    result['data_type'] = type(data).__name__
                    result['keys'] = list(data.keys()) if isinstance(data, dict) else None
                    
                    # Search for shareholding keywords
                    json_str = json.dumps(data, default=str).lower()
                    keywords = ['promoter', 'shareholding', 'holding pattern', 'fii', 'dii', 'public holding']
                    found_keywords = [kw for kw in keywords if kw in json_str]
                    
                    if found_keywords:
                        result['shareholding_keywords'] = found_keywords
                        result['has_shareholding_data'] = True
                        found_shareholding = True
                        
                        print(f"✅ {endpoint}")
                        print(f"   {description}")
                        print(f"   🎯 FOUND KEYWORDS: {found_keywords}")
                        if isinstance(data, dict) and data.keys():
                            print(f"   Keys: {list(data.keys())}")
                        print(f"   Preview: {json_str[:300]}...")
                    else:
                        print(f"✅ {endpoint} - {description}")
                        if isinstance(data, dict) and data.keys():
                            print(f"   Keys: {list(data.keys())[:5]}...")
                    
                except json.JSONDecodeError:
                    result['error'] = 'Invalid JSON'
                    print(f"⚠️  {endpoint} - Returned non-JSON data")
            else:
                print(f"❌ {endpoint} - Status {status}")
                result['error'] = f'HTTP {status}'
            
            results.append(result)
            time.sleep(0.5)  # Rate limiting
            
        except requests.exceptions.Timeout:
            print(f"⏱️  {endpoint} - Timeout")
            results.append({**result, 'error': 'Timeout'})
        except Exception as e:
            print(f"💥 {endpoint} - Error: {str(e)[:50]}")
            results.append({**result, 'error': str(e)[:100]})
        
        print()
    
    # Summary
    print("="*70)
    print("\nSUMMARY")
    print("="*70)
    
    successful = [r for r in results if r.get('success')]
    with_shareholding = [r for r in results if r.get('has_shareholding_data')]
    
    print(f"Total endpoints tested: {len(test_cases)}")
    print(f"Successful (200 OK): {len(successful)}")
    print(f"With shareholding data: {len(with_shareholding)}")
    
    if with_shareholding:
        print("\n🎉 FOUND SHAREHOLDING DATA IN:")
        for r in with_shareholding:
            print(f"  • {r['endpoint']}")
            print(f"    Keywords: {r['shareholding_keywords']}")
    else:
        print("\n❌ No shareholding data found in any endpoint")
        print("\nSuccessful endpoints (but no shareholding data):")
        for r in successful:
            print(f"  • {r['endpoint']} - {r['description']}")
    
    # Save results
    output_file = f'nse_comprehensive_test_{symbol}_{int(time.time())}.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Full results: {output_file}")
    
    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    if not found_shareholding:
        print("""
NSE shareholding data is NOT available via these public API endpoints.

Alternative approaches:

1. 🌐 MANUAL BROWSER INSPECTION (Most reliable)
   - Visit: https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE
   - Click "Shareholding Pattern" tab
   - Open DevTools > Network
   - Identify the XHR request
   
2. 🤖 SELENIUM AUTOMATION (If JavaScript-rendered)
   - Use Selenium to navigate the page
   - Extract data from rendered HTML
   - More robust but slower
   
3. 📁 BULK DOWNLOADS (If available)
   - Check NSE's bulk download section
   - Download quarterly CSV files
   - Parse and import
   
4. 💼 BSE ALTERNATIVE (Different exchange)
   - BSE may have more accessible APIs
   - Requires NSE→BSE symbol mapping
   - Check: https://www.bseindia.com/
   
5. 💰 COMMERCIAL APIS (Paid services)
   - Financial data providers
   - More reliable and maintained
   - Examples: Alphavantage, EOD, etc.
        """)


if __name__ == '__main__':
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'RELIANCE'
    test_all_endpoints(symbol)
