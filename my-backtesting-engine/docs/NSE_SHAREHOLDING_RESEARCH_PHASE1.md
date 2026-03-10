# Phase 1 Research Summary - NSE Shareholding Data

**Date**: January 28, 2026  
**Status**: ⚠️ Shareholding pattern data NOT available via public API  
**Scripts**: `nse_research_shareholding.py`, `nse_comprehensive_test.py`

---

## Executive Summary

After comprehensive testing of 17+ NSE API endpoints, we found that:
- ❌ **Shareholding pattern data is NOT available via public API endpoints**
- ✅ **Total shares outstanding IS available** via quote API
- ⚠️ **Shareholding patterns are filed as PDF/XBRL documents** in corporate announcements
- 💡 **Alternative approaches required** (manual scraping, BSE, or commercial APIs)

---

## Working Endpoints

### 1. Quote API ✅
- **URL**: `https://www.nseindia.com/api/quote-equity?symbol={SYMBOL}`
- **Success Rate**: 100%
- **Data Available**:
  - ✅ Total Shares Outstanding (`securityInfo.issuedSize`)
  - ✅ Company Name, Industry, ISIN
  - ✅ Face Value
  - ✅ Listing Date
  - ✅ Current Price, Market Cap

**Example Response**:
```json
{
  "securityInfo": {
    "issuedSize": 13532472634,
    "faceValue": 10,
    "boardStatus": "Main",
    "tradingStatus": "Active"
  }
}
```

### 2. Corporate Actions API ✅  
- **URL**: `https://www.nseindia.com/api/corporates-corporateActions?symbol={SYMBOL}&index=equities`
- **Success Rate**: 100%
- **Data**: Corporate actions (dividends, splits, etc.)
- **Note**: Does NOT contain shareholding pattern data

### 3. Corporate Announcements API ✅
- **URL**: `https://www.nseindia.com/api/corporate-announcements?symbol={SYMBOL}&index=equities`
- **Success Rate**: 100%
- **Data**: Links to PDF/XBRL filings
- **Note**: Shareholding patterns are filed here but as documents, not structured data
- **Challenge**: Would require PDF parsing or XBRL parsing

### 4. Chart Data API ✅
- **URL**: `https://www.nseindia.com/api/chart-databyindex?index={SYMBOL}&indices=false`
- **Success Rate**: 100%
- **Data**: OHLC chart data
- **Note**: No shareholding information

---

## Failed/Non-Existent Endpoints

Tested but returned 404 Not Found:
1. `/api/corporate-share-holdings` - 404
2. `/api/shareholding-pattern` - 404
3. `/api/corporates-shareholding` - 404
4. `/api/equity-shareholding` - 404
5. `/api/historical/securityArchives` - 404
6. `/api/company-master` - 404
7. `/api/companyMaster` - 404
8. `/api/company-info` - 404
9. `/api/corporate-info` - 404
10. `/api/quote-meta` - 404

---

## Key Findings

### 1. NSE's Data Architecture
- **Shareholding patterns are regulatory filings** submitted quarterly
- **Filed as PDF or XBRL documents**, not as structured JSON
- **Available through corporate announcements**, not dedicated API
- **Requires parsing** of documents to extract data

### 2. Anti-Scraping Measures Detected
- ✅ Cloudflare protection
- ✅ Cookie requirements (must visit homepage first)
- ✅ User-Agent validation
- ✅ Referer header checking
- ✅ Rate limiting (unclear threshold)

### 3. Data Availability
| Data Field | Available? | Source |
|------------|------------|--------|
| Total Shares Outstanding | ✅ YES | `quote-equity` API |
| Company Info (Name, ISIN, Industry) | ✅ YES | `quote-equity` API |
| Promoter Holding % | ❌ NO | Not in API |
| FII Holding % | ❌ NO | Not in API |
| DII Holding % | ❌ NO | Not in API |
| Public Holding % | ❌ NO | Not in API |
| Number of Shareholders | ❌ NO | Not in API |
| Shareholding Pattern History | ❌ NO | Not in API |

### 4. Announcement Categories
Analyzed 3,245 announcements for RELIANCE. Common categories:
- Loss of Share Certificates (673)
- Updates (479)
- Press Release (434)
- Analyst Meets (159)
- **Shareholders meeting (37)** - but not shareholding *patterns*

No dedicated "Shareholding Pattern" announcement category found.

---

## Recommended Path Forward

### ⭐ Option A: BSE API (RECOMMENDED)
**Why**: BSE (Bombay Stock Exchange) often has more accessible APIs than NSE

**Steps**:
1. Research BSE shareholding APIs
2. Create NSE ↔ BSE symbol mapping (may exist in `dhan_instruments.csv`)
3. Download from BSE instead of NSE
4. BSE URL: https://www.bseindia.com/

**Pros**:
- Potentially easier API access
- Same data (regulatory requirement)
- Well-documented

**Cons**:
- Requires symbol mapping
- May have different authentication

---

### Option B: Selenium Web Scraping
**Why**: If NSE shows data on website, we can extract it via browser automation

**Steps**:
1. Use Selenium WebDriver
2. Navigate to: `https://www.nseindia.com/get-quotes/equity?symbol={SYMBOL}`
3. Click "Shareholding Pattern" tab
4. Extract data from rendered HTML table
5. Handle JavaScript, cookies, anti-scraping

**Pros**:
- Can access any data visible on website
- Bypasses API limitations

**Cons**:
- Slower (needs full browser)
- Fragile (breaks with website changes)
- Requires headless browser setup
- Higher resource usage

---

### Option C: PDF Parsing from Announcements
**Why**: Shareholding patterns ARE filed, just as PDFs

**Steps**:
1. Use `corporate-announcements` API
2. Filter for shareholding pattern filings
3. Download PDFs
4. Parse using `pdfplumber` or `camelot`
5. Extract table data
6. Validate and structure

**Pros**:
- Official, regulatory data
- Historical data available
- No scraping concerns

**Cons**:
- PDF formats vary by company
- Parsing is complex and error-prone
- Slower (download + parse per company)
- May need OCR for scanned PDFs

---

### Option D: XBRL Parsing
**Why**: Companies file in XBRL format (machine-readable XML)

**Steps**:
1. Download XBRL filings from NSE
2. Parse using XBRL libraries (`python-xbrl`, `arelle`)
3. Extract shareholding pattern taxonomy
4. Structure data

**Pros**:
- Structured, machine-readable
- Standardized format (to some extent)
- Official regulatory data

**Cons**:
- XBRL is complex
- Taxonomy knowledge required
- Not all companies may use same schema
- Library dependencies

---

### Option E: Commercial Data Providers
**Why**: Pay for reliable, maintained data

**Examples**:
- **Alpha Vantage** (free tier + paid)
- **Financial Modeling Prep**
- **EOD Historical Data**
- **Quandl/Nasdaq Data Link**
- **IEX Cloud**

**Pros**:
- Reliable, maintained
- Structured, clean data
- API documentation
- Historical data
- Support

**Cons**:
- Costs money
- May have rate limits
- Dependency on third party

---

### Option F: Manual Browser Discovery (Required First)
**Why**: To find if there IS a hidden API endpoint

**Action Required** (15 minutes):
```
1. Open Chrome
2. Visit: https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE
3. Open DevTools (F12) > Network tab
4. Clear network log
5. Click "Shareholding Pattern" or "Company Info" tab
6. Look for XHR/Fetch requests
7. Check for any API calls with "shareholding" or "pattern"
8. Document the endpoint if found
```

If you find an endpoint, share it and we can build the downloader immediately.

---

## What We Can Build TODAY

Even without full shareholding data, we can build a **Partial Solution**:

### Available Now:
```python
# Data we CAN get from NSE API:
{
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries Limited",
    "isin": "INE002A01018",
    "industry": "Refineries & Marketing",
    "listing_date": "1995-11-29",
    "total_shares": 13532472634,
    "face_value": 10,
    "last_updated": "2026-01-28"
}
```

### Still Missing:
- ❌ Promoter holding %
- ❌ FII/DII holding %
- ❌ Public holding %
- ❌ Number of shareholders
- ❌ Historical trends

---

## Testing Summary

```
Total Endpoints Tested: 17
Successful (200 OK): 7
With Shareholding Data: 0
```

### Success Rate by Category:
- Quote/Price APIs: 100% (2/2)
- Corporate Data APIs: 66% (2/3)
- Chart/Market APIs: 100% (2/2)
- Shareholding-specific APIs: 0% (0/6)
- Master/Info APIs: 0% (0/4)

---

## Next Steps - Decision Required

**YOU NEED TO DECIDE**:

1. **Try BSE first?** (Option A - may be easier)
2. **Manual endpoint discovery?** (Option F - 15 min investment)
3. **Selenium scraping?** (Option B - more robust but slower)
4. **PDF/XBRL parsing?** (Options C/D - complex but official)
5. **Use commercial API?** (Option E - costs money)
6. **Proceed without shareholding data?** (Build with what we have)

**My Recommendation**: 
1. **First**: Try Option F (manual browser check) - 15 minutes
2. **Then**: Try Option A (BSE API) - potentially easier
3. **Fallback**: Option B (Selenium) if above don't work

---

## Files Created

1. `scripts/nse_research_shareholding.py` - Initial API testing script
2. `scripts/nse_comprehensive_test.py` - Comprehensive endpoint testing
3. `docs/NSE_SHAREHOLDING_RESEARCH_PHASE1.md` - This document
4. `nse_research_RELIANCE_*.json` - Test result outputs

---

## Code Artifacts

### Working NSE Session Setup:
```python
import requests

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json, */*',
    'Referer': 'https://www.nseindia.com/',
    'X-Requested-With': 'XMLHttpRequest',
})

# Initialize session (get cookies)
session.get('https://www.nseindia.com', timeout=10)

# Now you can make API calls
resp = session.get('https://www.nseindia.com/api/quote-equity', 
                   params={'symbol': 'RELIANCE'})
data = resp.json()
```

### Get Total Shares:
```python
def get_total_shares(symbol: str) -> int:
    """Get total shares outstanding for a symbol."""
    session = init_nse_session()  # as above
    
    resp = session.get(
        'https://www.nseindia.com/api/quote-equity',
        params={'symbol': symbol},
        timeout=15
    )
    resp.raise_for_status()
    
    data = resp.json()
    return data['securityInfo']['issuedSize']
```

---

**Phase 1 Status**: ✅ COMPLETE  
**Blocker**: Shareholding pattern APIs not publicly available  
**Recommendation**: Try BSE or manual browser discovery next  
**Time Invested**: ~2 hours
