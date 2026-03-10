import requests
import json

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def debug_bse_landing(code):
    url = f"https://www.bseindia.com/stock-share-price/shp/scripcode/{code}/flag/7/"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    r = session.get(url, headers=headers)
    print(f"BSE Landing Page for {code}: {r.status_code}")
    # print(r.text[:1000])
    
    # Check for dates
    import re
    dates = re.findall(r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}', r.text, re.IGNORECASE)
    print(f"Dates found: {dates}")
    
    # Check for XBRL links or similar
    links = re.findall(r'href=[\'"]?([^\'" >]+)', r.text)
    interesting = [l for l in links if 'XBRL' in l or 'xml' in l or 'shp' in l.lower()]
    print(f"Interesting links: {interesting}")

debug_bse_landing('544412')
